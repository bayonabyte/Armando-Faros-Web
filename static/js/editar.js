document.getElementById('marca').addEventListener('change', async function () {
    const marcaId = this.value;

    const modeloSelect = document.getElementById('modelo');

    if (!marcaId) {
        modeloSelect.innerHTML = '<option value="">Selecciona modelo</option>';
        return;
    }

    const response = await fetch(`/modelos?marca_id=${marcaId}`);
    const data = await response.json();

    modeloSelect.innerHTML = '<option value="">Selecciona modelo</option>';

    data.forEach(modelo => {
        const option = document.createElement('option');
        option.value = modelo.id;
        option.textContent = modelo.nombre;
        modeloSelect.appendChild(option);
    });
});


const tipoSelect = document.getElementById('tipo');
const grupoPosicion = document.getElementById('grupo_posicion');
const grupoLado = document.getElementById('grupo_lado');

const tiposPosicionYLado = [2, 3, 4, 5, 6, 8];
const tiposSoloLado = [7, 10];
const tiposSoloPosicion = [9];
const tiposNinguno = [1];

function actualizarCamposTipo(limpiar = false) {
    const tipoId = parseInt(tipoSelect.value);

    grupoPosicion.style.display = 'none';
    grupoLado.style.display = 'none';

    if (limpiar) {
        grupoPosicion.querySelector('select').value = "";
        grupoLado.querySelectorAll('input').forEach(i => i.checked = false);
    }

    grupoPosicion.querySelector('select').required = false;
    grupoLado.querySelectorAll('input').forEach(i => i.required = false);

    if (tiposPosicionYLado.includes(tipoId)) {
        grupoPosicion.style.display = 'block';
        grupoLado.style.display = 'block';

        grupoPosicion.querySelector('select').required = true;
        grupoLado.querySelectorAll('input').forEach(i => i.required = true);

    } else if (tiposSoloLado.includes(tipoId)) {
        grupoLado.style.display = 'block';
        grupoLado.querySelectorAll('input').forEach(i => i.required = true);

    } else if (tiposSoloPosicion.includes(tipoId)) {
        grupoPosicion.style.display = 'block';
        grupoPosicion.querySelector('select').required = true;
    }
}

tipoSelect.addEventListener('change', function () {
    actualizarCamposTipo(true);
});

document.addEventListener("DOMContentLoaded", function () {
    actualizarCamposTipo(false);
});