const REVIEWS = '/api/freshness-reviews';
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

function evidenceCard(claim) {
  const card = node('article', null, 'freshness-card');
  const heading = node('div', null, 'freshness-card-head');
  const verdict = node('span', claim.verdict, 'freshness-verdict');
  verdict.dataset.verdict = claim.verdict;
  heading.append(node('h3', claim.text), verdict);
  card.append(heading);
  if (claim.reason) card.append(node('p', claim.reason));
  if (claim.correction && !claim.reason?.includes(claim.correction)) {
    card.append(node('p', claim.correction));
  }
  const sources = claim.evidence || [];
  if (!sources.length) return card;
  const details = node('details');
  details.append(node('summary', `View ${sources.length} ${sources.length === 1 ? 'source' : 'sources'}`));
  for (const source of sources) {
    const item = node('div', null, 'freshness-source');
    item.append(sourceLink(source.title || 'Source excerpt', source.url));
    if (source.published_at) item.append(node('small', `${source.target} · Published ${source.published_at}`));
    if (source.excerpt) item.append(node('blockquote', source.excerpt));
    if (source.engine_manifest) item.append(sourceLink('Tagged package manifest', source.engine_manifest));
    details.append(item);
  }
  card.append(details);
  return card;
}

export function freshnessButton(api, question, citations) {
  const trigger = node('button', 'Check claim freshness', 'freshness-trigger');
  trigger.type = 'button';
  trigger.setAttribute('aria-haspopup', 'dialog');

  let dialog;
  const titleId = `freshness-title-${++dialogCount}`;
  const claim_versions = Object.fromEntries(citations.filter(c => Number.isInteger(c.version)).map(c => [c.claim_id, c.version]));
  const claim_ids = [...new Set(citations.map(c => c.claim_id).filter(Boolean))];

  function createDialog() {
    const panel = node('dialog', null, 'freshness-dialog');
    panel.setAttribute('aria-labelledby', titleId);
    panel.innerHTML = `
      <div class="freshness-heading">
        <div><h2 id="${titleId}">Claim freshness</h2><p class="freshness-question"></p></div>
        <button type="button" class="freshness-button" data-close autofocus>Close</button>
      </div>
      <p class="freshness-scope">Check the cited claims against saved Vite documentation on this device.</p>
      <form class="freshness-form">
        <label>Vite release<select name="target"><option>Vite 6</option><option selected>Vite 7</option></select></label>
        <label>As of date <span>(optional)</span><input name="as_of" type="date"></label>
        <button type="submit" class="freshness-button freshness-primary">Check claims</button>
      </form>
      <p class="freshness-status" role="status"></p>
      <div class="freshness-results"></div>
      <button type="button" class="freshness-button freshness-save" hidden>Save checks to this device</button>`;
    panel.querySelector('.freshness-question').textContent = question;
    const form = panel.querySelector('form');
    const run = form.querySelector('button');
    const results = panel.querySelector('.freshness-results');
    const status = panel.querySelector('[role="status"]');
    const save = panel.querySelector('.freshness-save');
    const target = form.elements.namedItem('target');
    const date = form.elements.namedItem('as_of');
    let busy = false;
    let checked;

    async function check(persist = false) {
      if (busy || (persist && !checked)) return;
      const scope = {claim_ids, claim_versions, target: target.value, as_of: date.value || null};
      busy = true;
      run.setAttribute('aria-disabled', 'true');
      save.setAttribute('aria-disabled', 'true');
      target.disabled = date.disabled = true;
      status.textContent = persist ? 'Saving checks…' : 'Checking cited claims…';
      status.classList.remove('is-error');
      try {
        const {reviews} = await api('POST', persist ? REVIEWS : `${REVIEWS}/preview`, scope);
        if (persist) {
          status.textContent = 'Checks saved to this device.';
        } else {
          const claims = reviews.flatMap(review => review.claims);
          results.replaceChildren(...claims.map(evidenceCard));
          checked = true;
          save.hidden = false;
          const allSaved = reviews.length > 0 && reviews.every(review => review.saved_at);
          status.textContent = `${claims.length} ${claims.length === 1 ? 'claim' : 'claims'} checked for ${scope.target}.${allSaved ? ' Checks are saved on this device.' : ''}`;
        }
      } catch (error) {
        status.textContent = error.message;
        status.classList.add('is-error');
      } finally {
        busy = false;
        run.removeAttribute('aria-disabled');
        save.removeAttribute('aria-disabled');
        target.disabled = date.disabled = false;
      }
    }

    form.addEventListener('input', () => {
      checked = false;
      results.replaceChildren();
      save.hidden = true;
      status.textContent = 'Select Check claims to check this release and date.';
      status.classList.remove('is-error');
    });
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
      trigger.after(dialog.panel);
    }
    dialog.panel.showModal();
    if (firstOpen) dialog.check();
  });
  return trigger;
}
