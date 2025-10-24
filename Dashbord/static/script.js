document.addEventListener('DOMContentLoaded', () => {

    // --- SÉLECTION DES ÉLÉMENTS DU DOM ---
    const searchInput = document.getElementById('searchInput');
    const yearFilter = document.getElementById('yearFilter');
    const marketFilter = document.getElementById('marketFilter');
    const resultsTitle = document.getElementById('resultsTitle');
    const dataTableBody = document.getElementById('dataTableBody');
    const exportCsvBtn = document.getElementById('exportCsvBtn');

    // Variable pour stocker l'instance du graphique
    let priceChartInstance = null;
    // Variable pour stocker toutes les données récupérées du serveur
    let allMercurialesData = [];

    // --- FONCTIONS ---

    /**
     * Récupère les données depuis notre API backend.
     */
    async function fetchData() {
        try {
            const response = await fetch('http://127.0.0.1:5000/api/data');
            if (!response.ok) {
                throw new Error(`Erreur HTTP! statut: ${response.status}`);
            }
            allMercurialesData = await response.json();
            console.log("Données récupérées avec succès :", allMercurialesData);
            updateDisplay(); // Met à jour l'affichage une fois les données chargées
        } catch (error) {
            console.error("Impossible de récupérer les données du backend:", error);
            resultsTitle.textContent = "Erreur : Le serveur backend n'est pas accessible.";
            dataTableBody.innerHTML = '<tr><td colspan="4">Assurez-vous que le serveur Python (app.py) est en cours d\'exécution.</td></tr>';
        }
    }

    /**
     * Filtre les données en fonction des critères choisis par l'utilisateur.
     */
    function filterData() {
        const searchTerm = searchInput.value.toLowerCase();
        const selectedYear = yearFilter.value;
        const selectedMarket = marketFilter.value;

        return allMercurialesData.filter(item => {
            const matchesSearch = item.produit.toLowerCase().includes(searchTerm);
            const matchesYear = selectedYear === 'all' || item.annee.toString() === selectedYear;
            const matchesMarket = selectedMarket === 'all' || item.marche === selectedMarket;

            return matchesSearch && matchesYear && matchesMarket;
        });
    }

    /**
     * Met à jour l'affichage du titre, du tableau et du graphique.
     */
    function updateDisplay() {
        const filteredData = filterData();

        // Mettre à jour le titre
        resultsTitle.textContent = `Résultats (${filteredData.length} trouvé(s))`;

        // Mettre à jour le tableau
        populateTable(filteredData);

        // Mettre à jour le graphique
        createChart(filteredData);
    }

    /**
     * Remplit le tableau avec les données filtrées.
     */
    function populateTable(data) {
        dataTableBody.innerHTML = ''; // Vider le tableau actuel

        if (data.length === 0) {
            dataTableBody.innerHTML = '<tr><td colspan="4">Aucune donnée trouvée pour ces critères.</td></tr>';
            return;
        }

        // Trier les données par date décroissante
        data.sort((a, b) => new Date(b.date) - new Date(a.date));

        data.forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date(item.date).toLocaleDateString('fr-FR')}</td>
                <td>${item.produit}</td>
                <td>${item.prix.toFixed(2)} €/${item.unite}</td>
                <td>${item.marche}</td>
            `;
            dataTableBody.appendChild(row);
        });
    }

    /**
     * Crée ou met à jour le graphique avec Chart.js.
     */
    function createChart(data) {
        const ctx = document.getElementById('priceChart').getContext('2d');

        // Grouper les données par produit pour le graphique
        const datasets = {};
        data.forEach(item => {
            if (!datasets[item.produit]) {
                datasets[item.produit] = {
                    label: item.produit,
                    data: [],
                    borderColor: getRandomColor(),
                    backgroundColor: 'rgba(0, 0, 0, 0)',
                    tension: 0.1
                };
            }
            datasets[item.produit].data.push({ x: item.date, y: item.prix });
        });

        const chartData = {
            datasets: Object.values(datasets)
        };

        if (priceChartInstance) {
            priceChartInstance.destroy();
        }

        priceChartInstance = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'month',
                            tooltipFormat: 'dd MMM yyyy'
                        },
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    },
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Prix (€/kg)'
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    },
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
    }
    
    /**
     * Génère et télécharge un fichier CSV avec les données filtrées.
     */
    function generateCSV() {
        const filteredData = filterData();
        if (filteredData.length === 0) {
            alert('Aucune donnée à exporter.');
            return;
        }

        const headers = ['Date', 'Produit', 'Prix (€/kg)', 'Unité', 'Marché', 'Année'];
        const csvRows = filteredData.map(item => [
            new Date(item.date).toLocaleDateString('fr-FR'),
            item.produit,
            item.prix.toFixed(2).replace('.', ','),
            item.unite,
            item.marche,
            item.annee
        ]);

        const csvContent = [
            headers.join(';'),
            ...csvRows.map(row => row.join(';'))
        ].join('\n');

        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', 'mercuriales_daf_reelles.csv');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function getRandomColor() {
        const letters = '0123456789ABCDEF';
        let color = '#';
        for (let i = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color;
    }

    // --- ÉCOUTEURS D'ÉVÉNEMENTS ---
    searchInput.addEventListener('input', updateDisplay);
    yearFilter.addEventListener('change', updateDisplay);
    marketFilter.addEventListener('change', updateDisplay);
    exportCsvBtn.addEventListener('click', generateCSV);

    // --- INITIALISATION ---
    // Lancer la récupération des données au chargement de la page
    fetchData();
});