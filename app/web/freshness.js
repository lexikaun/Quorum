const REVIEWS = '/api/freshness-reviews';
const verdicts = {
  superseded: 'Superseded',
  contradicted: 'Contradicted',
  unknown: 'Unverified',
  supported: 'Supported',
};
let dialogCount = 0;

function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (className) el.className = className;
  return el;
}

function sourceLink(text, href) {
  let url;
  try { url = new URL(href); } catch { return node('strong', text); }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') return node('strong', text);
  const link = node('a', text);
  link.href = url.href;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  return link;
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
}

function sourceNote(source, original = false) {
  const item = node('div', null, 'freshness-source');
  const title = original ? source.author || source.kind || 'Saved claim' : source.title || 'Source excerpt';
  const date = formatDate(original ? source.at : source.published_at);
  const meta = original ? date : [source.target, date ? 'Published ' + date : 'Publication date unavailable']
    .filter(Boolean).join(' · ');
  if (meta) item.append(node('small', meta));
  item.append(sourceLink(title, original ? source.ref : source.url));
  if (source.excerpt) item.append(node('blockquote', source.excerpt));
  if (source.engine_manifest) {
    item.append(sourceLink('Package manifest', source.engine_manifest));
    if (source.engine_excerpt) item.append(node('blockquote', source.engine_excerpt));
  }
  return item;
}

function claimRow(claim, source) {
  const row = node('details', null, 'freshness-claim');
  const summary = node('summary');
  const title = node('span', null, 'freshness-claim-title');
  title.append(node('strong', claim.text));
  if (source) {
    title.append(node('small', [source.author || source.kind, formatDate(source.at)].filter(Boolean).join(' · ')));
  }
  if (claim.reason) title.append(node('span', claim.reason, 'freshness-reason'));
  if (claim.next_step) title.append(node('span', claim.next_step, 'freshness-reason'));
  const verdict = node('span', verdicts[claim.verdict], 'freshness-verdict');
  verdict.dataset.verdict = claim.verdict;
  summary.append(title, verdict);
  row.append(summary);

  const body = node('div', null, 'freshness-evidence');
  if (claim.correction && !claim.reason?.includes(claim.correction)) {
    body.append(node('p', claim.correction, 'freshness-correction'));
  }
  const sources = claim.evidence || [];
  const comparison = node('div', null, 'freshness-comparison');
  if (source) {
    const original = node('div', null, 'freshness-original');
    original.append(node('h3', 'Saved in Quorum'), sourceNote(source, true));
    comparison.append(original);
  }
  const evidence = node('div');
  evidence.append(node('h3', 'Evidence used'));
  if (sources.length) evidence.append(...sources.map(entry => sourceNote(entry)));
  else evidence.append(node('p', 'No source established a verdict for this claim.'));
  comparison.append(evidence);
  body.append(comparison);
  row.append(body);
  return row;
}

function createTrigger(api, label, getContext, examples = []) {
  const isExample = examples.length > 0;
  const trigger = node('button', label, isExample ? 'freshness-examples' : 'btn freshness-trigger');
  trigger.type = 'button';
  trigger.setAttribute('aria-haspopup', 'dialog');
  const titleId = 'freshness-title-' + ++dialogCount;
  let dialog;

  function createDialog() {
    const panel = node('dialog', null, 'freshness-dialog');
    panel.setAttribute('aria-labelledby', titleId);
    panel.innerHTML = `
      <div class="freshness-heading">
        <div>
          <h2 id="${titleId}">Claim freshness</h2>
          <p class="freshness-question"></p>
        </div>
        <button type="button" class="btn ghost freshness-button" data-close>Close</button>
      </div>
      <div class="freshness-workspace">
        <form class="freshness-form">
          <label class="freshness-example-picker" hidden>Saved example<select name="example"></select></label>
          <label>Vite release<select name="target"><option value="Vite 6">Vite 6.0</option><option value="Vite 7" selected>Vite 7.0</option></select></label>
          <label>Evidence source<select name="source_mode"><option value="replay">Saved docs</option><option value="public">Official docs</option></select></label>
          <label>As of date <span>(optional)</span><input name="as_of" type="date" aria-describedby="${titleId}-scope"></label>
          <button type="submit" class="btn primary freshness-button">Check claims</button>
          <p class="freshness-scope" id="${titleId}-scope"></p>
        </form>
        <div class="freshness-review">
          <h3>Claim results</h3>
          <div class="freshness-counts" aria-label="Verdict counts" hidden></div>
          <p class="freshness-status" role="status"></p>
          <p class="freshness-provenance" hidden></p>
          <div class="freshness-results"></div>
        </div>
      </div>
      <div class="freshness-footer" hidden>
        <span class="freshness-saved"></span>
        <button type="button" class="btn freshness-button freshness-save">Save checks to this device</button>
      </div>`;
    const form = panel.querySelector('form');
    const run = form.querySelector('button');
    const storage = panel.querySelector('.freshness-saved');
    const footer = panel.querySelector('.freshness-footer');
    const results = panel.querySelector('.freshness-results');
    const counts = panel.querySelector('.freshness-counts');
    const status = panel.querySelector('[role="status"]');
    const provenance = panel.querySelector('.freshness-provenance');
    const save = panel.querySelector('.freshness-save');
    const example = form.elements.namedItem('example');
    const target = form.elements.namedItem('target');
    const date = form.elements.namedItem('as_of');
    const mode = form.elements.namedItem('source_mode');
    const scopeHint = panel.querySelector('.freshness-scope');
    date.max = new Date().toISOString().slice(0, 10);
    let busy = false;
    let checkedScope;

    if (isExample) {
      example.parentElement.hidden = false;
      examples.forEach(({title}, index) => example.add(new Option(title, index)));
    } else {
      example.disabled = true;
    }

    function setStatus(message, error = false) {
      status.textContent = message;
      status.classList.toggle('is-error', error);
    }

    function clearResults() {
      checkedScope = null;
      counts.hidden = footer.hidden = true;
      provenance.hidden = true;
      results.replaceChildren();
      storage.textContent = '';
      save.hidden = false;
    }

    function updateHint() {
      scopeHint.textContent = mode.value === 'public'
        ? 'Checks known passages online. Your claims stay on this device.'
        : 'Checks Node.js compatibility and default build targets offline.';
      if (date.value) scopeHint.textContent += ' Only evidence available by this date is eligible.';
    }

    function selectExample() {
      const context = getContext(example.value);
      panel.querySelector('.freshness-question').textContent = context.question;
      target.value = 'Vite 7';
      date.value = context.asOf || '';
      updateHint();
    }

    async function check(persist = false) {
      if (busy || (persist && !checkedScope)) return;
      const {citations} = getContext(example.value);
      const claim_ids = [...new Set(citations.map(c => c.claim_id).filter(Boolean))];
      if (!claim_ids.length) {
        clearResults();
        setStatus('These saved example claims are unavailable on this device.', true);
        return;
      }
      const claim_versions = Object.fromEntries(citations.filter(c => Number.isInteger(c.version)).map(c => [c.claim_id, c.version]));
      const scope = persist ? checkedScope : {
        claim_ids, claim_versions, target: target.value, as_of: date.value || null, source_mode: mode.value,
      };
      busy = true;
      target.disabled = date.disabled = mode.disabled = example.disabled = true;
      run.setAttribute('aria-disabled', 'true');
      save.setAttribute('aria-disabled', 'true');
      if (!persist) clearResults();
      setStatus(persist ? 'Saving results…' : mode.value === 'public' ? 'Checking official documentation…' : 'Checking saved documentation…');
      try {
        const {reviews, preview_id} = await api('POST', persist ? REVIEWS : REVIEWS + '/preview', scope);
        if (persist) {
          storage.textContent = 'Saved on this device';
          save.hidden = true;
          setStatus('Checks saved to this device.');
          return;
        }
        const entries = reviews.flatMap(review => review.claims.map(claim => ({claim, source: review.source})));
        const ordered = Object.keys(verdicts).flatMap(verdict => entries.filter(entry => entry.claim.verdict === verdict));
        const rows = ordered.map(({claim, source}) => claimRow(claim, source));
        if (rows[0] && window.matchMedia('(min-width: 651px)').matches) rows[0].open = true;
        results.replaceChildren(...rows);
        counts.replaceChildren(...Object.entries(verdicts).flatMap(([verdict, title]) => {
          const count = entries.filter(entry => entry.claim.verdict === verdict).length;
          if (!count) return [];
          const badge = node('span', count + ' ' + title.toLowerCase(), 'freshness-verdict');
          badge.dataset.verdict = verdict;
          return [badge];
        }));
        const checked = rows.length > 0;
        checkedScope = checked ? {...scope, preview_id} : null;
        counts.hidden = footer.hidden = !checked;
        const saved = checked && reviews.every(review => review.saved_at);
        storage.textContent = saved ? 'Saved on this device' : 'These checks stay on this device.';
        save.hidden = saved;
        const count = entries.length;
        setStatus(count ? count + (count === 1 ? ' claim reviewed for ' : ' claims reviewed for ') + scope.target + '.0' +
          (scope.as_of ? ' as of ' + formatDate(scope.as_of) : '') + '.' : 'Quorum found no claims to check.');
        provenance.hidden = !checked;
        provenance.textContent = scope.source_mode === 'replay'
          ? 'Saved docs captured ' + formatDate(reviews[0]?.snapshot_at)
          : 'Official docs checked ' + formatDate(reviews[0]?.checked_at);
      } catch (error) {
        setStatus(error.message, true);
      } finally {
        busy = false;
        target.disabled = date.disabled = mode.disabled = false;
        example.disabled = !isExample;
        run.removeAttribute('aria-disabled');
        save.removeAttribute('aria-disabled');
      }
    }

    function updateScope() {
      clearResults();
      updateHint();
      setStatus('Select Check claims to review this release and date.');
    }

    selectExample();
    example.addEventListener('change', () => { selectExample(); check(); });
    target.addEventListener('change', updateScope);
    mode.addEventListener('change', updateScope);
    date.addEventListener('input', updateScope);
    form.addEventListener('submit', event => { event.preventDefault(); check(); });
    save.addEventListener('click', () => check(true));
    panel.querySelector('[data-close]').addEventListener('click', () => panel.close());
    panel.addEventListener('close', () => { if (!panel.open && trigger.isConnected) trigger.focus(); });
    return {panel, check};
  }

  trigger.addEventListener('click', () => {
    const firstOpen = !dialog;
    if (firstOpen) {
      dialog = createDialog();
      (isExample ? trigger.parentElement : trigger).after(dialog.panel);
    }
    dialog.panel.showModal();
    if (firstOpen) dialog.check();
  });
  return trigger;
}

export function freshnessButton(api, question, citations) {
  return createTrigger(api, 'Check claim freshness', () => ({question, citations}));
}

export function freshnessExamples(api, examples, getClaim) {
  return createTrigger(api, 'Try freshness examples', index => {
    const example = examples[Number(index)];
    const citations = example.claim_ids.map(getClaim);
    return {question: example.question, citations: citations.every(Boolean) ? citations : [], asOf: example.as_of};
  }, examples);
}
