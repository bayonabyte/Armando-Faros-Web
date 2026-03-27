function eliminarProducto(id, codigo) {

    if (!confirm("¿Seguro que deseas eliminar el producto " + codigo + "?")) {
        return;
    }

    fetch(`/eliminar_producto/${id}`, {
        method: "POST"
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("Producto eliminado correctamente");
            location.reload(); // recarga la tabla
        } else {
            alert(data.error || "Error al eliminar producto");
        }
    })
    .catch(error => {
        console.error("Error:", error);
        alert("Error en la petición");
    });
}