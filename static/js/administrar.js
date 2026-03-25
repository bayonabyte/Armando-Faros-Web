function verProducto(id) {
    fetch(`/producto/${id}`)
        .then(res => res.json())
        .then(data => {

            console.log(data); // 👈 útil para depurar

            document.getElementById("detalle").innerHTML = `
                ${data.imagen ? `<img src="/static/uploads/${data.imagen}" style="width:150px; display:block; margin-bottom:10px;">` : ""}
                Código: ${data.codigo || '-'}<br>
                Marca: ${data.marca || '-'}<br>
                Modelo: ${data.modelo || '-'}<br>
                Compra: ${data.precio_compra || 0}<br>
                Venta: ${data.precio_venta || 0}<br>
                Stock: ${data.stock || 0}
            `;

            document.getElementById("modal").style.display = "block";
        })
        .catch(error => {
            console.error("Error al obtener el producto:", error);
        });
}

function cerrarModal() {
    document.getElementById("modal").style.display = "none";
}