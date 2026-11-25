// Ask for confirmation before changing a rental to Returned.
document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.getAttribute('data-confirm'))) event.preventDefault();
  });
});
