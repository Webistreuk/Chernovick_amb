(function () {
  const appointmentBtn = document.getElementById('appointment-btn');
  if (!appointmentBtn) return;

  appointmentBtn.addEventListener('click', () => {
    appointmentBtn.classList.add('disabled');
    setTimeout(() => appointmentBtn.classList.remove('disabled'), 1500);
  });
})();