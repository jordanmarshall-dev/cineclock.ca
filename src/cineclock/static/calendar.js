// Close the date picker after choosing a day, or when tapping anywhere else.
(() => {
  const pop = document.querySelector(".cal-pop");
  if (!pop) return;
  pop.addEventListener("click", (e) => {
    if (e.target.closest("a")) pop.open = false;
  });
  document.addEventListener("click", (e) => {
    if (!pop.contains(e.target)) pop.open = false;
  });
})();
