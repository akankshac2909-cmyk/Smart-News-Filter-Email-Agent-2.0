document.addEventListener('DOMContentLoaded', () => {
  const interestsInput = document.getElementById('interests');
  const emailInput = document.getElementById('email');
  const filterBtn = document.getElementById('filterBtn');
  const statusDiv = document.getElementById('status');

  // Load saved settings
  chrome.storage.local.get(['interests', 'email'], (result) => {
    if (result.interests) interestsInput.value = result.interests;
    if (result.email) emailInput.value = result.email;
  });

  filterBtn.addEventListener('click', async () => {
    const interests = interestsInput.value.trim();
    const email = emailInput.value.trim();

    if (!email) {
      statusDiv.innerText = "Please enter an email address.";
      statusDiv.style.color = "#ef4444";
      return;
    }

    // Save settings
    chrome.storage.local.set({ interests, email });

    statusDiv.innerText = "Scraping Google News...";
    statusDiv.style.color = "#3b82f6";

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab.url.includes("news.google.com")) {
        statusDiv.innerText = "Please navigate to news.google.com";
        statusDiv.style.color = "#ef4444";
        return;
      }

      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });

      chrome.tabs.sendMessage(tab.id, { action: "scrape" }, async (response) => {
        if (!response || !response.articles) {
          statusDiv.innerText = "Could not find articles on this page.";
          statusDiv.style.color = "#ef4444";
          return;
        }

        const articles = response.articles;
        statusDiv.innerText = `Analyzing ${articles.length} articles with Agent...`;

        try {
          const decisions = await runAgent(articles, interests, email);

          statusDiv.innerText = "Applying filter to page...";
          chrome.tabs.sendMessage(tab.id, { action: "apply_filter", decisions }, () => {
            statusDiv.innerText = "Feed Cleaned & Email Sent! 🚀";
            statusDiv.style.color = "#10b981";
          });
        } catch (apiError) {
          statusDiv.innerText = "Agent Error: " + apiError.message;
          statusDiv.style.color = "#ef4444";
        }
      });
    } catch (e) {
      statusDiv.innerText = "Extension Error: " + e.message;
      statusDiv.style.color = "#ef4444";
    }
  });
});

async function runAgent(articles, interests, email) {
  const endpoint = `http://localhost:5000/filter`;
  
  // Send a minimal subset to save bandwidth and tokens
  const payloadArticles = articles.map(a => ({ id: a.id, title: a.title, snippet: a.snippet }));

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ articles: payloadArticles, interests, email })
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || `Python Server Error: ${response.status}`);
  }

  return await response.json();
}
