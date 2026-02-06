(function () {
    const generateForm = document.getElementById('generate');
    if (generateForm) {
        generateForm.addEventListener('submit', function () {
            document.getElementById('overlay').style.display = 'block';
        });
    }
})();