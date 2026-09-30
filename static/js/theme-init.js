// A téma beállítása még a CSS betöltése előtt, hogy ne villanjon fel a világos oldal sötét módban
(function () {
    try {
        var preference = localStorage.getItem('arena-theme') || 'auto';
        var dark = preference === 'dark'
            || (preference === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
        document.documentElement.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
    } catch (error) {
        // localStorage nem elérhető: marad a világos téma
    }
})();
