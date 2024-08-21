var rowCount = 0; // Initialize row count

function addRow() {
    rowCount++; // Increment row count each time a row is added
    var table = document.getElementById("dataInputTable");
    var newRow = table.insertRow(-1); // Adds a row at the end of the table

    // Iterate through the configTypeList JavaScript object
    for (const [column, type] of Object.entries(configTypeList)) {
        var cell = newRow.insertCell(-1);
        cell.innerHTML = `<input type="text" class="form-control" name="${column}[${rowCount}]" placeholder="${type}">`;
    }
}

document.addEventListener("DOMContentLoaded", function() {
    for (let i = 0; i < 5; i++) {
        addRow();
    }
});
