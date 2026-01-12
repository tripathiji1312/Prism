document.addEventListener("DOMContentLoaded", () => {
  // 1. Select Elements
  const menuTrigger = document.getElementById("menuTrigger");
  const sideMenu = document.getElementById("sideMenu");
  const backdrop = document.getElementById("backdrop");
  const closeBtn = document.getElementById("closeMenuBtn");

  // 2. Function to Toggle Menu
  function toggleMenu(isOpen) {
    if (isOpen) {
      sideMenu.classList.add("active");
      backdrop.classList.add("active");
    } else {
      sideMenu.classList.remove("active");
      backdrop.classList.remove("active");
    }
  }

  // 3. Event Listeners
  if (menuTrigger) {
    menuTrigger.addEventListener("click", (e) => {
      // CRITICAL FIX: Stops the page from reloading/redirecting
      e.preventDefault();
      toggleMenu(true);
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => toggleMenu(false));
  }

  if (backdrop) {
    // Closes menu if you click the dark background area
    backdrop.addEventListener("click", () => toggleMenu(false));
  }
});

