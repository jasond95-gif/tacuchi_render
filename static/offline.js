// Clave en localStorage para guardar pedidos pendientes
const STORAGE_KEY = "tacuchi_pedidos_pendientes";

// Obtener pedidos pendientes desde localStorage
function getPendingOrders() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const data = JSON.parse(raw);
    return Array.isArray(data) ? data : [];
  } catch (e) {
    console.log("Error leyendo pedidos pendientes:", e);
    return [];
  }
}

// Guardar pedidos pendientes en localStorage
function setPendingOrders(pedidos) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pedidos || []));
  } catch (e) {
    console.log("Error guardando pedidos pendientes:", e);
  }
}

// Muestra/oculta un banner simple
function setOfflineBanner(online) {
  const banner = document.getElementById("offline-banner");
  if (!banner) return;
  if (online) {
    banner.classList.remove("show");
    banner.textContent = "Modo online: pedidos se guardan directamente en el servidor.";
  } else {
    banner.classList.add("show");
    banner.textContent = "Modo offline: pedidos se guardan en el celular y se sincronizan luego.";
  }
}

// Construye un objeto de pedido a partir del DOM (carrito)
function buildOrderFromDOM() {
  const mesaInput = document.getElementById("mesa-input");
  const mesa = mesaInput ? mesaInput.value.trim() : "N/A";
  const table = document.getElementById("cart-table");
  if (!table) return null;

  const rows = table.querySelectorAll("tbody tr.cart-row");
  if (!rows.length) return null;

  const items = [];
  rows.forEach(row => {
    const name = row.getAttribute("data-name") || "";
    const qty = parseFloat(row.getAttribute("data-qty") || "0");
    const subtotal = parseFloat(row.getAttribute("data-subtotal") || "0");
    if (name && qty > 0) {
      items.push({ name, qty, subtotal });
    }
  });

  if (!items.length) return null;

  // Tomamos el total desde el DOM
  const totalSpan = document.getElementById("cart-total-value");
  let total = 0;
  if (totalSpan) {
    total = parseFloat(totalSpan.getAttribute("data-total") || "0");
  }

  return {
    fecha_hora: new Date().toISOString().replace("T", " ").substring(0, 19),
    mesa: mesa || "N/A",
    total: total || 0,
    items: items
  };
}

// Interceptar el envío del formulario de pedido para manejar OFFLINE
function setupOfflineOrderHandling() {
  const form = document.getElementById("form-pedido");
  if (!form) return;

  form.addEventListener("submit", function (e) {
    if (navigator.onLine) {
      // Modo online normal: dejamos que el formulario vaya al servidor
      return;
    }

    // Modo offline: prevenimos envío y guardamos localmente
    e.preventDefault();

    const order = buildOrderFromDOM();
    if (!order) {
      alert("No hay productos en el pedido para guardar offline.");
      return;
    }

    const pending = getPendingOrders();
    pending.push(order);
    setPendingOrders(pending);

    alert("Pedido guardado offline en el celular. Se sincronizará cuando vuelva la conexión.");

    // Opcional: recargar la página para limpiar el carrito visualmente
    window.location.href = "/";
  });
}

// Intentar sincronizar pedidos pendientes cuando volvemos a estar online
async function syncPendingOrdersIfAny() {
  if (!navigator.onLine) return;

  const pending = getPendingOrders();
  if (!pending.length) return;

  try {
    const response = await fetch("/api/sync_pedidos_offline", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ pedidos: pending }),
    });

    if (!response.ok) throw new Error("Respuesta no OK del servidor");

    const data = await response.json();
    console.log("Sincronización offline OK:", data);
    setPendingOrders([]); // Limpiar pedidos pendientes

    const banner = document.getElementById("offline-banner");
    if (banner) {
      banner.classList.add("show");
      banner.textContent = `Se sincronizaron ${data.synced || 0} pedidos offline.`;
      setTimeout(() => {
        banner.classList.remove("show");
      }, 4000);
    }
  } catch (err) {
    console.log("Error sincronizando pedidos offline:", err);
  }
}

window.addEventListener("load", () => {
  setOfflineBanner(navigator.onLine);
  setupOfflineOrderHandling();
  syncPendingOrdersIfAny();
});

window.addEventListener("online", () => {
  setOfflineBanner(true);
  syncPendingOrdersIfAny();
});

window.addEventListener("offline", () => {
  setOfflineBanner(false);
});
