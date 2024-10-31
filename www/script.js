function updateData() {
    fetch('/data')
        .then(response => response.json())
        .then(data => {
            document.getElementById('temperature').textContent = data.temperature + '°C';
            document.getElementById('humidity').textContent = data.humidity + '%';
            document.getElementById('fan_speed').textContent = data.fan_speed;
        })
        .catch(error => console.error('Error fetching data:', error));
}

// Aktualisiere die Daten alle 5 Sekunden
setInterval(updateData, 5000);

// Initialer Aufruf
updateData();
