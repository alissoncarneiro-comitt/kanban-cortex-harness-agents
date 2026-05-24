/**
 * Cockpit Markdown Renderer — FEAT-014
 * Parser read-only com sanitização allowlist e suporte Mermaid.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.CockpitMarkdown = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const ALLOWED_TAGS = new Set([
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'pre', 'code', 'blockquote', 'a', 'strong', 'em', 'hr', 'div', 'span', 'br',
  ]);

  function escHtml(text) {
    return String(text ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatInlineMarkdown(text) {
    let out = escHtml(text);
    out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
      const safeUrl = String(url).trim();
      if (/^(https?:|mailto:|#)/i.test(safeUrl)) {
        return `<a href="${escHtml(safeUrl)}" rel="noopener noreferrer" target="_blank">${escHtml(label)}</a>`;
      }
      return escHtml(label);
    });
    return out;
  }

  function isTableRow(line) {
    const t = line.trim();
    return t.startsWith('|') && t.endsWith('|');
  }

  function isTableSeparator(line) {
    return /^\|[\s|:-]+\|$/.test(line.trim());
  }

  function parseTableRow(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
  }

  function renderTable(rows) {
    if (!rows.length) return '';
    const header = rows[0];
    let body = rows.slice(1);
    if (body.length && isTableSeparator('|' + body[0].join('|') + '|')) {
      body = body.slice(1);
    }
    const thead = `<thead><tr>${header.map(c => `<th>${formatInlineMarkdown(c)}</th>`).join('')}</tr></thead>`;
    const tbody = body.length
      ? `<tbody>${body.map(row => `<tr>${row.map(c => `<td>${formatInlineMarkdown(c)}</td>`).join('')}</tr>`).join('')}</tbody>`
      : '';
    return `<div class="md-table-wrap"><table>${thead}${tbody}</table></div>`;
  }

  function renderRichMarkdown(markdown) {
    const lines = String(markdown || '').split(/\r?\n/);
    const html = [];
    let i = 0;
    const listStack = [];

    function closeList() {
      while (listStack.length) {
        html.push('</ul>');
        listStack.pop();
      }
    }

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      if (!trimmed) {
        closeList();
        i += 1;
        continue;
      }

      const fence = trimmed.match(/^```(\w+)?\s*$/);
      if (fence) {
        closeList();
        const lang = (fence[1] || '').toLowerCase();
        const codeLines = [];
        i += 1;
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i]);
          i += 1;
        }
        if (lang === 'mermaid') {
          html.push(`<div class="mermaid">${escHtml(codeLines.join('\n'))}</div>`);
        } else {
          html.push(`<pre><code>${escHtml(codeLines.join('\n'))}</code></pre>`);
        }
        i += 1;
        continue;
      }

      if (isTableRow(line)) {
        closeList();
        const tableRows = [];
        while (i < lines.length && isTableRow(lines[i])) {
          tableRows.push(parseTableRow(lines[i]));
          i += 1;
        }
        html.push(renderTable(tableRows));
        continue;
      }

      const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        closeList();
        const level = heading[1].length;
        html.push(`<h${level}>${formatInlineMarkdown(heading[2])}</h${level}>`);
        i += 1;
        continue;
      }

      if (trimmed.startsWith('>')) {
        closeList();
        const quoteLines = [];
        while (i < lines.length && lines[i].trim().startsWith('>')) {
          quoteLines.push(lines[i].trim().replace(/^>\s?/, ''));
          i += 1;
        }
        html.push(`<blockquote><p>${formatInlineMarkdown(quoteLines.join(' '))}</p></blockquote>`);
        continue;
      }

      const bullet = line.match(/^(\s*)[-*+]\s+(.+)$/);
      if (bullet) {
        const indent = bullet[1].length;
        const depth = Math.floor(indent / 2);
        while (listStack.length > depth + 1) {
          html.push('</ul>');
          listStack.pop();
        }
        while (listStack.length < depth + 1) {
          html.push('<ul>');
          listStack.push(depth);
        }
        html.push(`<li>${formatInlineMarkdown(bullet[2])}</li>`);
        i += 1;
        continue;
      }

      if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
        closeList();
        html.push('<hr>');
        i += 1;
        continue;
      }

      closeList();
      html.push(`<p>${formatInlineMarkdown(line)}</p>`);
      i += 1;
    }

    closeList();
    return html.join('');
  }

  function sanitizeHtml(html) {
    const template = document.createElement('template');
    template.innerHTML = html;
    const walk = (node) => {
      Array.from(node.childNodes).forEach((child) => {
        if (child.nodeType === Node.TEXT_NODE) return;
        if (child.nodeType !== Node.ELEMENT_NODE) {
          child.remove();
          return;
        }
        const tag = child.tagName.toLowerCase();
        if (!ALLOWED_TAGS.has(tag)) {
          child.replaceWith(document.createTextNode(child.textContent || ''));
          return;
        }
        Array.from(child.attributes).forEach((attr) => {
          const name = attr.name.toLowerCase();
          if (name.startsWith('on') || name === 'style') {
            child.removeAttribute(attr.name);
            return;
          }
          if (tag === 'a' && name === 'href') {
            const href = attr.value.trim();
            if (!/^(https?:|mailto:|#)/i.test(href)) {
              child.removeAttribute(attr.name);
            }
          } else if (!['href', 'rel', 'target', 'class', 'aria-hidden'].includes(name)) {
            child.removeAttribute(attr.name);
          }
        });
        walk(child);
      });
    };
    walk(template.content);
    return template.innerHTML;
  }

  function sanitizeHtmlServer(html) {
    let out = String(html || '');
    out = out.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');
    out = out.replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '');
    return out;
  }

  function renderLegacyMarkdown(markdown) {
    const lines = String(markdown || '').split(/\r?\n/);
    const html = [];
    let inList = false;
    let inCode = false;
    let codeLines = [];
    function closeList() {
      if (inList) {
        html.push('</ul>');
        inList = false;
      }
    }
    lines.forEach((line) => {
      if (line.trim().startsWith('```')) {
        if (inCode) {
          html.push(`<pre><code>${escHtml(codeLines.join('\n'))}</code></pre>`);
          codeLines = [];
          inCode = false;
        } else {
          closeList();
          inCode = true;
        }
        return;
      }
      if (inCode) {
        codeLines.push(line);
        return;
      }
      if (!line.trim()) {
        closeList();
        return;
      }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        closeList();
        const level = heading[1].length;
        html.push(`<h${level}>${formatInlineMarkdown(heading[2])}</h${level}>`);
        return;
      }
      const bullet = line.match(/^[-*]\s+(.+)$/);
      if (bullet) {
        if (!inList) {
          html.push('<ul>');
          inList = true;
        }
        html.push(`<li>${formatInlineMarkdown(bullet[1])}</li>`);
        return;
      }
      closeList();
      html.push(`<p>${formatInlineMarkdown(line)}</p>`);
    });
    if (inCode) html.push(`<pre><code>${escHtml(codeLines.join('\n'))}</code></pre>`);
    closeList();
    return html.join('');
  }

  function renderMarkdown(markdown, options) {
    const rich = options && options.rich;
    const raw = rich ? renderRichMarkdown(markdown) : renderLegacyMarkdown(markdown);
    if (typeof document !== 'undefined') {
      return sanitizeHtml(raw);
    }
    return sanitizeHtmlServer(raw);
  }

  let mermaidLoadPromise = null;

  function loadMermaid() {
    if (typeof window === 'undefined') return Promise.resolve(null);
    if (window.mermaid) return Promise.resolve(window.mermaid);
    if (mermaidLoadPromise) return mermaidLoadPromise;
    mermaidLoadPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
      script.async = true;
      script.onload = () => {
        if (window.mermaid) {
          window.mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'strict' });
          resolve(window.mermaid);
        } else {
          reject(new Error('mermaid unavailable'));
        }
      };
      script.onerror = () => reject(new Error('mermaid load failed'));
      document.head.appendChild(script);
    });
    return mermaidLoadPromise;
  }

  async function scheduleMermaidRender(container) {
    if (!container || typeof document === 'undefined') return;
    const nodes = container.querySelectorAll('.mermaid');
    if (!nodes.length) return;
    try {
      const mermaid = await loadMermaid();
      await mermaid.run({ nodes: Array.from(nodes) });
    } catch (err) {
      nodes.forEach((node) => {
        node.classList.add('mermaid-error');
        node.insertAdjacentHTML(
          'beforeend',
          `<p class="mermaid-error-msg">${escHtml(err.message || 'Mermaid render failed')}</p>`,
        );
      });
    }
  }

  return {
    escHtml,
    formatInlineMarkdown,
    renderRichMarkdown,
    renderLegacyMarkdown,
    renderMarkdown,
    sanitizeHtml,
    sanitizeHtmlServer,
    scheduleMermaidRender,
    ALLOWED_TAGS,
  };
}));
