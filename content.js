// Scrape articles from Google News
function scrapeGoogleNews() {
  const articles = [];
  const seenTitles = new Set();
  
  // Use a very specific selector for the "News Cards" to avoid nested duplicates
  const containers = document.querySelectorAll('.IFHyqb, .UW0SDc');
  
  containers.forEach((container, index) => {
    // Find the primary headline link - specifically the one with the title text
    const link = container.querySelector('.JtKRv');
    if (!link) return;

    const title = link.innerText.trim();
    
    // Deduplicate: If we already seen this exact title, skip it
    if (seenTitles.has(title)) return;
    seenTitles.add(title);

    let url = link.href || link.getAttribute('href') || '#';
    
    if (title && title.length > 5) {
      const id = `agentic-news-${index}`;
      container.setAttribute('data-agent-id', id);

      // Convert relative to absolute URLs
      if (url.startsWith('./')) {
        url = 'https://news.google.com' + url.substring(1);
      } else if (url.startsWith('/') && !url.startsWith('//') && !url.startsWith('http')) {
        url = 'https://news.google.com' + url;
      }

      articles.push({ id, title, snippet: "", url });
    }
  });
  
  console.log(`[Agent Scraper] Found ${articles.length} unique news items.`);
  return articles;
}

// Apply styling based on Agent decisions
function processAgentDecisions(decisions) {
  decisions.forEach(decision => {
    const node = document.querySelector(`article[data-agent-id="${decision.id}"]`);
    if (!node) return;

    if (node.querySelector('.agent-tag')) return;

    const tag = document.createElement('div');
    tag.className = 'agent-tag';
    tag.style.fontSize = '12px';
    tag.style.fontWeight = 'bold';
    tag.style.padding = '4px 8px';
    tag.style.marginBottom = '8px';
    tag.style.borderRadius = '6px';
    tag.style.display = 'inline-block';
    tag.style.fontFamily = 'sans-serif';

    if (!decision.isKept) {
      node.style.opacity = '0.15';
      node.style.filter = 'grayscale(100%) blur(2px)';
      node.style.transition = 'all 0.5s ease';
      
      node.addEventListener('mouseenter', () => {
        node.style.opacity = '1';
        node.style.filter = 'none';
      });
      node.addEventListener('mouseleave', () => {
        node.style.opacity = '0.15';
        node.style.filter = 'grayscale(100%) blur(2px)';
      });

      tag.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
      tag.style.color = '#ef4444';
      tag.style.border = '1px solid #ef4444';
      tag.innerText = `🛑 Filtered: ${decision.reasoning}`;
      node.prepend(tag);
    } else {
      node.style.borderLeft = '4px solid #a855f7';
      node.style.paddingLeft = '12px';
      node.style.backgroundColor = 'rgba(168, 85, 247, 0.05)';
      node.style.transition = 'all 0.3s ease';
      
      tag.style.backgroundColor = 'rgba(168, 85, 247, 0.1)';
      tag.style.color = '#a855f7';
      tag.style.border = '1px solid #a855f7';
      tag.innerText = `✨ High Impact: ${decision.reasoning}`;
      node.prepend(tag);
    }
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "scrape") {
    sendResponse({ articles: scrapeGoogleNews() });
  } else if (request.action === "apply_filter") {
    processAgentDecisions(request.decisions);
    sendResponse({ success: true });
  }
  return true;
});
