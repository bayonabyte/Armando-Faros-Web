function retirarProducto(codigo, stock) {

    // 🔴 1. CONFIRMACIÓN PRIMERO
    if (!confirm("⚠️ Estás retirando el producto con código " + codigo + ".\n¿Deseas continuar?")) {
        return;
    }

    let cantidad = 1;

    // 🟡 2. SI HAY MÁS DE 1 → PEDIR CANTIDAD
    if (stock > 1) {
        cantidad = prompt("¿Cuántas unidades deseas retirar?\nStock disponible: " + stock);

        if (cantidad === null) return; // canceló

        cantidad = parseInt(cantidad);

        if (isNaN(cantidad) || cantidad <= 0) {
            alert("Cantidad inválida");
            return;
        }

        if (cantidad > stock) {
            alert("No puedes retirar más de lo disponible");
            return;
        }
    }

    // 🟢 3. ENVIAR
    fetch("/retirar", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: `codigo=${codigo}&cantidad=${cantidad}`
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            mostrarNotificacion("Retiro realizado correctamente");
            setTimeout(() => location.reload(), 1000);
        } else {
            alert(data.error);
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