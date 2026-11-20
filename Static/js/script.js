document.addEventListener('DOMContentLoaded', () => {
  const locateBtn = document.getElementById('locateBtn');
  const locationInput = document.getElementById('locationInput');
  if (locateBtn && locationInput) {
    locateBtn.addEventListener('click', () => {
      if (!navigator.geolocation) { locationInput.placeholder = 'Location unavailable—enter manually'; return; }
      locateBtn.disabled = true; locateBtn.textContent = 'Finding location…';
      navigator.geolocation.getCurrentPosition(async (position) => {
        const {latitude, longitude} = position.coords;
        // Coordinates are stored as a practical location label; reverse-geocoding is not automatic.
        locationInput.value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`;
        locateBtn.textContent = 'Location added'; locateBtn.disabled = false;
      }, () => { locateBtn.textContent = 'Location permission denied'; locateBtn.disabled = false; }, {timeout:10000, enableHighAccuracy:false});
    });
  }
  const messages = document.getElementById('messages');
  if (messages) messages.scrollTop = messages.scrollHeight;
});
