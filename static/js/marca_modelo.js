document.addEventListener("DOMContentLoaded", function () {
    cambiarFormulario(); // 🔥 se ejecuta al cargar
});

function cambiarFormulario() {
    let tipoSelect = document.getElementById("tipo");
    let tipo = tipoSelect.value;

    // 🔥 asignar al hidden SIEMPRE
    document.getElementById("tipo_hidden").value = tipo;

    let seccionMarca = document.getElementById("seccion_marca");
    let seccionModelo = document.getElementById("seccion_modelo");
    let selectMarca = document.querySelector("select[name='marca_id']");

    if (tipo === "marca_modelo") {
        seccionMarca.style.display = "block";
        seccionModelo.style.display = "none";

        selectMarca.disabled = true;
        selectMarca.value = "";
    } else {
        seccionMarca.style.display = "none";
        seccionModelo.style.display = "block";

        selectMarca.disabled = false;
    }
}