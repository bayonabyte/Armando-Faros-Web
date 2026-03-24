function confirmarRetiro(codigo) {
    return confirm(
        "⚠️ CONFIRMACIÓN DE RETIRO\n\n" +
        "Código: " + codigo + "\n\n" +
        "Esta acción eliminará el producto del inventario.\n\n" +
        "¿Desea continuar?"
    );
}

function retirarProducto(codigo, boton) {

    if (!confirm("⚠️ Está retirando el producto con código " + codigo + ".\n¿Desea continuar?")) {
        return;
    }

    fetch("/retirar", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: "codigo=" + codigo
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {

            mostrarNotificacion("Producto eliminado correctamente");

            setTimeout(() => {
                location.reload();
            }, 1000);

        } else {
            mostrarNotificacion("Error al eliminar");
        }
    });
}

function mostrarNotificacion(mensaje) {
    const notif = document.getElementById("notificacion");

    notif.innerText = mensaje;
    notif.classList.add("mostrar");

    setTimeout(() => {
        notif.classList.remove("mostrar");
    }, 3000);
}