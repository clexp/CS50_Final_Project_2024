document.addEventListener("DOMContentLoaded", function () {
  const tagSearch = document.getElementById("tagSearch");
  const tagAutocomplete = document.getElementById("tagAutocomplete");
  const selectedTags = document.getElementById("selectedTags");

  if (!tagSearch) return;

  // Initialize tag list
  let allTags = [];

  // Fetch tags from server once at startup
  fetch("/tags/search")
    .then((response) => response.json())
    .then((tags) => {
      allTags = tags;
    });

  // Handle tag search input
  tagSearch.addEventListener("input", function () {
    const query = this.value.trim().toLowerCase();
    if (query.length < 1) {
      tagAutocomplete.style.display = "none";
      return;
    }

    // Filter tags client-side
    const matches = allTags
      .filter((tag) => tag.toLowerCase().includes(query))
      .slice(0, 10); // Limit to top 10 matches

    tagAutocomplete.innerHTML = matches
      .map(
        (tag) => `
				<div class="p-2 cursor-pointer hover-bg-light" 
					 onclick="addTag('${tag}')">
					${tag}
				</div>
			`
      )
      .join("");

    tagAutocomplete.style.display = "block";
  });

  // Add tag function
  window.addTag = function (tagName) {
    if (document.querySelector(`input[name="tags"][value="${tagName}"]`)) {
      tagSearch.value = "";
      tagAutocomplete.style.display = "none";
      return;
    }

    const badge = document.createElement("span");
    badge.className = "badge bg-primary me-2 mb-2";
    badge.innerHTML = `
			${tagName}
			<button type="button" class="btn-close btn-close-white" 
					aria-label="Remove"></button>
			<input type="hidden" name="tags" value="${tagName}">
		`;

    // Add click handler directly to the badge
    badge.querySelector(".btn-close").addEventListener("click", function () {
      badge.remove();
      // Optionally submit the form to refresh results
      if (document.getElementById("searchForm")) {
        document.getElementById("searchForm").submit();
      }
    });

    selectedTags.appendChild(badge);
    tagSearch.value = "";
    tagAutocomplete.style.display = "none";
  };

  // Set up handlers for existing close buttons
  document.querySelectorAll("#selectedTags .btn-close").forEach((button) => {
    button.addEventListener("click", function () {
      const badge = this.closest(".badge");
      if (badge) {
        badge.remove();
        // Optionally submit the form to refresh results
        if (document.getElementById("searchForm")) {
          document.getElementById("searchForm").submit();
        }
      }
    });
  });

  // Close autocomplete when clicking outside
  document.addEventListener("click", function (e) {
    if (!tagSearch.contains(e.target) && !tagAutocomplete.contains(e.target)) {
      tagAutocomplete.style.display = "none";
    }
  });
});
