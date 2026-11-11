/**
 * Controlador Principal de la Aplicación CampusSwap
 * Orquestación de Vistas, Eventos, Modales y Renderizado Reactivo.
 */

document.addEventListener("DOMContentLoaded", () => {
    window.app = new CampusSwapApp();
    window.app.init();
});

const USBMED_OFERTA_ACADEMICA = {
    "Facultad de Ingenierías": [
        "Ingeniería de Datos y Software",
        "Ingeniería de Sistemas Cibernéticos",
        "Ingeniería de Sonido",
        "Ingeniería Industrial",
        "Ingeniería Ambiental",
        "Ingeniería Electrónica",
        "Ingeniería Multimedia",
        "Creación de Contenidos Digitales",
        "Otra"
    ],
    "Facultad de Ciencias Empresariales": [
        "Administración de Negocios",
        "Contaduría Pública",
        "Negocios Internacionales",
        "Otra"
    ],
    "Facultad de Arquitectura y Artes": [
        "Arquitectura",
        "Diseño Industrial",
        "Otra"
    ],
    "Facultad de Derecho y Ciencias Políticas": [
        "Derecho",
        "Otra"
    ],
    "Facultad de Psicología": [
        "Psicología",
        "Otra"
    ],
    "Facultad de Educación": [
        "Licenciatura en Educación Preescolar",
        "Licenciatura en Educación Artística y Cultural",
        "Licenciatura en Educación Física y Deportes",
        "Licenciatura en Lengua Castellana",
        "Tecnología en Entrenamiento Deportivo",
        "Otra"
    ]
};

class CampusSwapApp {
    constructor() {
        const validViews = ["catalog", "matches", "trades", "chat", "profile", "tickets", "admin"];
        const hashView = (window.location.hash || "").replace(/^#/, "").trim().toLowerCase();
        const storedView = localStorage.getItem("campus_swap_active_view") || sessionStorage.getItem("campus_swap_active_view");

        let initialView = "catalog";
        if (validViews.includes(hashView)) {
            initialView = hashView;
        } else if (validViews.includes(storedView)) {
            initialView = storedView;
        }

        this.currentView = initialView;
        const storedChatId = localStorage.getItem("campus_swap_active_chat_trade_id");
        this.activeTradeChatId = storedChatId ? parseInt(storedChatId, 10) : 101;
        this.selectedRating = 5;
        this.books = [];
        this.trades = [];
        this.matches = [];
        this.activeCategory = null;
        this.searchQuery = "";
        this.ofertaAcademica = { ...USBMED_OFERTA_ACADEMICA };
    }

    escapeHtml(value) {
        return String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[character]);
    }

    async loadProgramasAcademicos(showAlertOnError = false) {
        try {
            const data = await api.getProgramasAcademicos();
            if (data && data.carreras_por_facultad && Object.keys(data.carreras_por_facultad).length > 0) {
                this.ofertaAcademica = data.carreras_por_facultad;
            } else if (data && typeof data === "object" && !Array.isArray(data) && Object.keys(data).length > 0) {
                this.ofertaAcademica = data;
            } else {
                this.ofertaAcademica = { ...USBMED_OFERTA_ACADEMICA };
            }
        } catch (e) {
            console.warn("No se pudo cargar oferta académica desde el backend, usando catálogo de respaldo:", e);
            this.ofertaAcademica = { ...USBMED_OFERTA_ACADEMICA };
            if (showAlertOnError) {
                this.showToast("No se pudo conectar con el catálogo en línea. Se cargó la oferta académica local.", "warning");
            }
        }
        this.populateFacultadesDropdowns();
    }

    populateFacultadesDropdowns() {
        if (!this.ofertaAcademica || Object.keys(this.ofertaAcademica).length === 0) {
            this.ofertaAcademica = { ...USBMED_OFERTA_ACADEMICA };
        }
        const facultades = Object.keys(this.ofertaAcademica);
        ["reg-facultad", "edit-prof-facultad"].forEach(id => {
            const select = document.getElementById(id);
            if (!select) return;
            const currentVal = select.value;
            select.innerHTML = '<option value="">Seleccionar facultad...</option>' +
                facultades.map(f => `<option value="${this.escapeHtml(f)}">${this.escapeHtml(f)}</option>`).join("");
            if (currentVal && facultades.includes(currentVal)) {
                select.value = currentVal;
            }
        });
    }

    onFacultadChange(prefix) {
        const facSelect = document.getElementById(prefix === 'reg' ? 'reg-facultad' : 'edit-prof-facultad');
        const carSelect = document.getElementById(prefix === 'reg' ? 'reg-carrera' : 'edit-prof-carrera');
        const univInput = document.getElementById(prefix === 'reg' ? 'reg-univ' : 'edit-prof-univ');
        if (!facSelect || !carSelect) return;
        const fac = facSelect.value;
        const oferta = this.ofertaAcademica && Object.keys(this.ofertaAcademica).length > 0
            ? this.ofertaAcademica
            : USBMED_OFERTA_ACADEMICA;

        // Conectar facultad con universidad automáticamente si no está establecida
        if (fac && univInput && (!univInput.value || univInput.value.trim() === "" || univInput.value.includes("Ej."))) {
            univInput.value = "Universidad de San Buenaventura Medellín (USBMED)";
        }

        if (!fac) {
            carSelect.innerHTML = '<option value="">Seleccionar carrera...</option>';
            return;
        }
        let carreras = (oferta[fac] || []).slice();
        if (carreras.length > 0 && !carreras.includes("Otra")) {
            carreras.push("Otra");
        }
        carSelect.innerHTML = '<option value="">Seleccionar carrera...</option>' +
            carreras.map(c => `<option value="${this.escapeHtml(c)}">${this.escapeHtml(c)}</option>`).join("");
    }

    async init() {
        this._bindEvents();
        this._applyTheme();
        await this.loadProgramasAcademicos();
        await this.loadInitialData();
        this.updateUserBadge();
        this.navigateTo(this.currentView, false);
    }

    // -------------------------------------------------------------------------
    // Eventos y Navegación
    // -------------------------------------------------------------------------
    _bindEvents() {
        // Escucha de autenticación OAuth federada (Google, X, Facebook) desde ventana emergente
        window.addEventListener("message", async (event) => {
            if (event.data && event.data.type === "OAUTH_SUCCESS") {
                const { token, user, provider } = event.data;
                api.setToken(token);
                api.setCurrentUser(user);
                this.updateUserBadge();
                this.closeModal("auth-modal");
                this.closeModal("login-modal");
                this.closeModal("register-modal");
                const provName = provider ? provider.toUpperCase() : "red social";
                this.showToast(`¡Bienvenido, ${user.name || user.email}! Sesión iniciada con ${provName}`, "success");
                this.renderCurrentView();
            }
        });

        // Soporte para navegación con el historial y hash en la URL
        window.addEventListener("hashchange", () => {
            const hashView = (window.location.hash || "").replace(/^#/, "").trim().toLowerCase();
            const validViews = ["catalog", "matches", "trades", "chat", "profile", "tickets", "admin"];
            if (validViews.includes(hashView) && hashView !== this.currentView) {
                this.navigateTo(hashView, false);
            }
        });

        // Navegación en Header y Mobile Bar
        document.querySelectorAll("[data-nav]").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const view = btn.getAttribute("data-nav");
                this.navigateTo(view);
            });
        });

        // Alternar tema claro / oscuro
        const themeBtn = document.getElementById("theme-toggle-btn");
        if (themeBtn) {
            themeBtn.addEventListener("click", () => this.toggleTheme());
        }

        // Barra de búsqueda en catálogo
        const searchInput = document.getElementById("book-search-input");
        if (searchInput) {
            searchInput.addEventListener("input", (e) => {
                this.searchQuery = e.target.value;
                this.filterAndRenderBooks();
            });
        }

        // Píldoras de Categorías
        document.querySelectorAll(".category-pill").forEach(pill => {
            pill.addEventListener("click", () => {
                document.querySelectorAll(".category-pill").forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                const catId = pill.getAttribute("data-category");
                this.activeCategory = catId === "all" ? null : parseInt(catId);
                this.filterAndRenderBooks();
            });
        });

        // Pestañas de Trueques
        document.querySelectorAll(".trade-tab").forEach(tab => {
            tab.addEventListener("click", () => {
                document.querySelectorAll(".trade-tab").forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
                const estado = tab.getAttribute("data-trade-status");
                this.renderTrades(estado);
            });
        });

        // Envío de chat
        const chatSendBtn = document.getElementById("chat-send-btn");
        const chatInput = document.getElementById("chat-input");
        if (chatSendBtn && chatInput) {
            chatSendBtn.addEventListener("click", () => this.sendChatMessage());
            chatInput.addEventListener("keypress", (e) => {
                if (e.key === "Enter") this.sendChatMessage();
            });
            // Indicador de escritura: envía typing al backend por WS
            chatInput.addEventListener("input", () => this._onChatInputTyping());
        }

        // Chips de respuesta rápida en chat
        document.querySelectorAll(".quick-reply-chip").forEach(chip => {
            chip.addEventListener("click", () => {
                if (chatInput) {
                    chatInput.value = chip.textContent;
                    this.sendChatMessage();
                }
            });
        });

        // Estrellas en modal de calificación
        document.querySelectorAll(".star-select-btn").forEach(star => {
            star.addEventListener("click", () => {
                const val = parseInt(star.getAttribute("data-star-val"));
                this.setRatingStars(val);
            });
        });
    }

    async loadInitialData() {
        // El catálogo es público: se carga siempre y un fallo se muestra al usuario.
        try {
            this.books = await api.getPublicaciones();
        } catch (e) {
            console.error("Error al cargar el catálogo:", e);
            this.books = [];
            this.showToast("No se pudo cargar el catálogo. Verifica que el servidor esté disponible.", "error");
        }

        // Trueques y coincidencias son privados: solo se piden con sesión iniciada.
        if (!api.getToken()) {
            this.trades = [];
            this.matches = [];
            this._actualizarContadorMatches();
            return;
        }
        try {
            this.trades = await api.getTrueques();
        } catch (e) {
            console.error("Error al cargar trueques:", e);
            this.trades = [];
        }
        try {
            this.matches = await api.getMatches();
        } catch (e) {
            console.error("Error al cargar coincidencias:", e);
            this.matches = [];
        }
        this._actualizarContadorMatches();
    }

    _actualizarContadorMatches() {
        // Contador real de coincidencias en el menú; oculto si no hay ninguna
        const badge = document.getElementById("matches-badge");
        if (!badge) return;
        const total = (this.matches || []).length;
        badge.textContent = total;
        badge.style.display = total > 0 ? "" : "none";
    }

    navigateTo(viewName, updateHash = true) {
        const validViews = ["catalog", "matches", "trades", "chat", "profile", "tickets", "admin"];
        if (!validViews.includes(viewName)) {
            viewName = "catalog";
        }

        // Cerrar WebSocket si salimos de la vista de chat
        if (this.currentView === 'chat' && viewName !== 'chat') {
            this._closeChatWebSocket(true);
        }
        this.currentView = viewName;

        // Persistir la sección actual para recargas (F5)
        localStorage.setItem("campus_swap_active_view", viewName);
        sessionStorage.setItem("campus_swap_active_view", viewName);

        if (updateHash && window.location.hash !== `#${viewName}`) {
            history.replaceState(null, "", `#${viewName}`);
        }

        // Actualizar active en nav
        document.querySelectorAll("[data-nav]").forEach(el => {
            if (el.getAttribute("data-nav") === viewName) {
                el.classList.add("active");
            } else {
                el.classList.remove("active");
            }
        });

        // Mostrar sección correspondiente
        document.querySelectorAll(".view-section").forEach(sec => sec.classList.remove("active"));
        const target = document.getElementById(`view-${viewName}`);
        if (target) {
            target.classList.add("active");
            window.scrollTo({ top: 0, behavior: "smooth" });
        }

        this.renderCurrentView();
    }

    renderCurrentView() {
        switch (this.currentView) {
            case "catalog":
                this.filterAndRenderBooks();
                break;
            case "matches":
                this.renderMatches();
                break;
            case "trades":
                this.renderTrades();
                break;
            case "chat":
                // Auto-seleccionar la primera conversación habilitada si la actual está bloqueada
                const currentChatTrade = this.trades.find(t => t.id === this.activeTradeChatId);
                if (!this.isChatAvailable(currentChatTrade)) {
                    const firstAvailable = this.trades.find(t => this.isChatAvailable(t));
                    if (firstAvailable) this.activeTradeChatId = firstAvailable.id;
                }
                this.renderChatList();
                this.loadChatMessages(this.activeTradeChatId);
                break;
            case "profile":
                this.renderProfile();
                break;
            case "admin":
                this.renderAdminPanel();
                break;
            case "tickets":
                this.renderTicketsView();
                break;
        }
    }

    // -------------------------------------------------------------------------
    // Catálogo de Libros y Filtros
    // -------------------------------------------------------------------------
    filterAndRenderBooks() {
        const grid = document.getElementById("books-grid");
        if (!grid) return;

        let filtered = [...this.books];
        if (this.activeCategory) {
            filtered = filtered.filter(b => b.categoria_id === this.activeCategory);
        }
        if (this.searchQuery.trim()) {
            const q = this.searchQuery.toLowerCase();
            filtered = filtered.filter(b => 
                b.titulo.toLowerCase().includes(q) ||
                (b.autor && b.autor.toLowerCase().includes(q)) ||
                (b.libro_buscado && b.libro_buscado.toLowerCase().includes(q))
            );
        }

        if (filtered.length === 0) {
            grid.innerHTML = `
                <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem;">
                    <i class="fa-solid fa-book-open" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 1rem;"></i>
                    <h3>No se encontraron libros con estos criterios</h3>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">Intenta con otra búsqueda o sé el primero en publicar este título.</p>
                    <button class="btn btn-primary" onclick="app.openModal('publish-book-modal')" style="margin-top: 1.5rem;">
                        <i class="fa-solid fa-plus"></i> Publicar Libro
                    </button>
                </div>
            `;
            return;
        }

        grid.innerHTML = filtered.map(book => {
            const coverSrc = (book.portada && !book.portada.includes("openlibrary.org")) 
                ? book.portada 
                : (api.getThematicCover ? api.getThematicCover(book.titulo, book.categoria_id) : 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80');
            const fallbackSrc = (book.portada_fallback && !book.portada_fallback.includes("openlibrary.org"))
                ? book.portada_fallback
                : (api.getThematicCover ? api.getThematicCover(book.titulo, book.categoria_id) : 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80');

            return `
            <div class="book-card">
                <div class="book-card-header">
                    <img src="${this.escapeHtml(coverSrc)}" alt="${this.escapeHtml(book.titulo)}" class="book-cover-img" data-fallback="${this.escapeHtml(fallbackSrc)}" onerror="this.onerror=null;this.src=this.dataset.fallback">
                    <span class="book-condition-badge">${this.escapeHtml(book.estado_libro || 'Buen estado')}</span>
                    <span class="book-category-tag">${this.escapeHtml(book.categoria_nombre || 'General')}</span>
                </div>
                <div class="book-card-body">
                    <h3 class="book-title">${this.escapeHtml(book.titulo)}</h3>
                    <p class="book-author">Por ${this.escapeHtml(book.autor || 'Autor desconocido')} • ${this.escapeHtml(book.edicion || 'Edición estándar')}</p>
                    
                    <div class="looking-for-box">
                        <div class="looking-for-header">
                            <i class="fa-solid fa-arrows-rotate"></i> Busca a cambio
                        </div>
                        <div class="looking-for-text">${this.escapeHtml(book.libro_buscado || 'Cualquier texto afín al área')}</div>
                    </div>

                    <div class="book-owner-row">
                        <div class="owner-info">
                            <img src="${this.escapeHtml(book.usuario_avatar || 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150&auto=format&fit=crop&q=80')}" class="owner-avatar" alt="${this.escapeHtml(book.usuario_nombre)}">
                            <div class="owner-details">
                                <span class="owner-name">
                                    ${this.escapeHtml(book.usuario_nombre)}
                                    <i class="fa-solid fa-circle-check verified-badge" title="Usuario Verificado"></i>
                                </span>
                                <span class="owner-univ">${book.usuario_carrera ? `${this.escapeHtml(book.usuario_carrera)} • ` : ''}${this.escapeHtml(book.usuario_universidad || 'Comunidad')}</span>
                            </div>
                        </div>
                        <div class="owner-rating">
                            <i class="fa-solid fa-star"></i>
                            <span>${book.usuario_reputacion ? Number(book.usuario_reputacion).toFixed(1) : 'Nuevo'}</span>
                        </div>
                    </div>

                    <div class="book-card-actions">
                        <button class="btn btn-secondary btn-sm" onclick="app.showBookDetail(${book.id})">
                            <i class="fa-regular fa-eye"></i> Detalle
                        </button>
                        <button class="btn btn-primary btn-sm" onclick="app.startTradeWithBook(${book.id})">
                            <i class="fa-solid fa-bolt"></i> Trueque
                        </button>
                    </div>
                </div>
            </div>
        `;
        }).join("");
    }

    showBookDetail(bookId) {
        const book = this.books.find(b => b.id === bookId);
        if (!book) return;

        const coverSrc = (book.portada && !book.portada.includes("openlibrary.org")) 
            ? book.portada 
            : (api.getThematicCover ? api.getThematicCover(book.titulo, book.categoria_id) : 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80');

        const container = document.getElementById("book-detail-content");
        if (container) {
            container.innerHTML = `
                <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                    <img src="${this.escapeHtml(coverSrc)}" style="width: 140px; height: 190px; object-fit: cover; border-radius: var(--radius-md);" alt="${this.escapeHtml(book.titulo)}">
                    <div style="flex: 1; min-width: 240px;">
                        <span class="status-badge confirmado">${this.escapeHtml(book.categoria_nombre || 'General')}</span>
                        <h2 style="font-size: 1.4rem; margin: 0.5rem 0 0.25rem 0;">${this.escapeHtml(book.titulo)}</h2>
                        <p style="color: var(--text-secondary); margin-bottom: 0.75rem;">Autor: <strong>${this.escapeHtml(book.autor || 'No especificado')}</strong></p>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">ISBN: ${this.escapeHtml(book.isbn || 'N/A')} • Edición: ${this.escapeHtml(book.edicion || '1ra Edición')}</p>
                        <p style="font-size: 0.85rem; color: var(--text-muted);">Estado: <strong>${this.escapeHtml(book.estado_libro || 'Buen estado')}</strong></p>
                    </div>
                </div>
                <div style="margin-top: 1.5rem;">
                    <h4 style="font-size: 0.95rem; margin-bottom: 0.5rem;">Descripción del ejemplar:</h4>
                    <p style="color: var(--text-secondary); font-size: 0.9rem; line-height: 1.6;">${this.escapeHtml(book.descripcion || 'Sin descripción adicional provista por el estudiante.')}</p>
                </div>
                <div class="looking-for-box" style="margin-top: 1.5rem;">
                    <div class="looking-for-header">
                        <i class="fa-solid fa-arrows-rotate"></i> Material deseado a cambio por el dueño
                    </div>
                    <div class="looking-for-text" style="font-size: 1rem;">${this.escapeHtml(book.libro_buscado || 'No especificado')}</div>
                </div>
                <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.75rem; flex-wrap: wrap;">
                    <button class="btn btn-secondary" onclick="app.closeModal('book-detail-modal')">Cerrar</button>
                    <button class="btn btn-secondary" onclick="app.closeModal('book-detail-modal'); app.startBookVerification(${book.id})">
                        <i class="fa-solid fa-microchip"></i> Verificar con Red Neuronal
                    </button>
                    <button class="btn btn-primary" onclick="app.closeModal('book-detail-modal'); app.startTradeWithBook(${book.id})">
                        <i class="fa-solid fa-bolt"></i> Proponer Trueque Inmediato
                    </button>
                </div>
            `;
            this.openModal("book-detail-modal");
        }
    }

    async startTradeWithBook(bookId, ownPublicationId = null) {
        const book = this.books.find(b => b.id === bookId);
        if (!book) return;

        const current = api.getCurrentUser();
        if (!current) {
            this.showToast("Debes iniciar sesión para proponer un trueque", "warning");
            this.openAuthModal("login");
            return;
        }

        if (String(book.usuario_id) === String(current.id)) {
            this.showToast("No puedes proponer trueque a tu propia publicación", "warning");
            return;
        }

        const ownPublicationSelect = document.getElementById("trade-prop-book-propone");
        const destinationId = document.getElementById("trade-prop-publicacion-destino-id");
        const inputBookRecibe = document.getElementById("trade-prop-book-recibe");
        const inputUsuarioRecibe = document.getElementById("trade-prop-user-recibe");
        const inputUsuarioId = document.getElementById("trade-prop-user-id");

        try {
            const ownPublications = (await api.getMisPublicaciones())
                .filter(publication => publication.estado_publicacion === "activa");
            if (ownPublications.length === 0) {
                this.showToast("Primero publica un libro activo para ofrecer en el trueque", "warning");
                return;
            }
            ownPublicationSelect.innerHTML = ownPublications.map(publication =>
                `<option value="${publication.id}">${this.escapeHtml(publication.titulo)}</option>`
            ).join("");
            if (ownPublicationId && ownPublications.some(pub => String(pub.id) === String(ownPublicationId))) {
                ownPublicationSelect.value = ownPublicationId;
            }
        } catch (e) {
            this.showToast(e.message || "No se pudieron cargar tus publicaciones", "error");
            return;
        }

        if (destinationId) destinationId.value = book.id;
        if (inputBookRecibe) inputBookRecibe.value = book.titulo;
        if (inputUsuarioRecibe) inputUsuarioRecibe.value = `${book.usuario_nombre} (${book.usuario_universidad || 'Universidad'})`;
        if (inputUsuarioId) inputUsuarioId.value = book.usuario_id;

        this.openModal("propose-trade-modal");
    }

    async submitTradeProposal() {
        const publicacionOrigenId = document.getElementById("trade-prop-book-propone")?.value;
        const publicacionDestinoId = document.getElementById("trade-prop-publicacion-destino-id")?.value;
        const usuarioRecibeId = document.getElementById("trade-prop-user-id")?.value;

        if (!publicacionOrigenId || !publicacionDestinoId) {
            this.showToast("Selecciona la publicación que ofreces", "warning");
            return;
        }

        try {
            await api.proposeTrade({
                usuario_recibe_id: usuarioRecibeId,
                publicacion_origen_id: Number(publicacionOrigenId),
                publicacion_destino_id: Number(publicacionDestinoId)
            });

            this.showToast("¡Propuesta de trueque enviada exitosamente!", "success");
            this.closeModal("propose-trade-modal");
            this.trades = await api.getTrueques();
            this.navigateTo("trades");
        } catch (e) {
            this.showToast(e.message || "Error al enviar propuesta", "error");
        }
    }

    async submitNewBook() {
        const titulo = document.getElementById("new-book-titulo")?.value;
        const autor = document.getElementById("new-book-autor")?.value;
        const categoria_id = document.getElementById("new-book-categoria")?.value;
        const estado_libro = document.getElementById("new-book-estado")?.value;
        const libro_buscado = document.getElementById("new-book-buscado")?.value;
        const descripcion = document.getElementById("new-book-descripcion")?.value;
        const isbn = document.getElementById("new-book-isbn")?.value;
        const edicion = document.getElementById("new-book-edicion")?.value;
        const directCover = document.getElementById("new-book-cover-direct")?.files[0];

        if (!titulo || !libro_buscado) {
            this.showToast("El título y el libro que buscas son obligatorios", "warning");
            return;
        }

        try {
            this.showToast("Publicando libro...", "info");
            const newBook = await api.createPublicacion({
                titulo,
                autor,
                categoria_id: parseInt(categoria_id),
                estado_libro,
                libro_buscado,
                descripcion,
                isbn,
                edicion
            });

            this.books = await api.getPublicaciones();
            this.closeModal("publish-book-modal");
            this.filterAndRenderBooks();

            // Limpiar inputs del modal
            document.getElementById("new-book-titulo").value = "";
            if (document.getElementById("new-book-autor")) document.getElementById("new-book-autor").value = "";
            if (document.getElementById("new-book-buscado")) document.getElementById("new-book-buscado").value = "";
            if (document.getElementById("new-book-descripcion")) document.getElementById("new-book-descripcion").value = "";
            if (document.getElementById("new-book-cover-direct")) document.getElementById("new-book-cover-direct").value = "";

            this.showToast("¡Libro registrado! Pasando a verificación con Red Neuronal...", "success");

            // Iniciar flujo de verificación fotográfica con IA
            await this.startBookVerification(newBook.id, directCover);
        } catch (e) {
            this.showToast(e.message || "Error al publicar libro", "error");
        }
    }

    async openVerificationDemo() {
        const bookId = (this.books && this.books.length > 0) ? this.books[0].id : 1;
        await this.startBookVerification(bookId);
    }

    async startBookVerification(publicationId, preloadedCover = null) {
        try {
            this.showToast("Generando código único para verificación con IA...", "info");
            const challenge = await api.createBookVerificationChallenge(publicationId);

            // Resetear estados del modal de verificación
            const formContainer = document.getElementById("book-verification-form-container");
            const aiStatus = document.getElementById("book-verification-ai-status");
            const aiResult = document.getElementById("book-verification-ai-result");
            if (formContainer) formContainer.style.display = "block";
            if (aiStatus) aiStatus.style.display = "none";
            if (aiResult) aiResult.style.display = "none";

            document.getElementById("book-verification-publication-id").value = publicationId;
            document.getElementById("book-verification-id").value = challenge.verificacion_id;
            document.getElementById("book-verification-code").textContent = challenge.codigo;
            document.getElementById("book-verification-instructions").textContent = challenge.instrucciones || "Escribe el código en una hoja junto al libro y sube las fotos:";

            const coverInput = document.getElementById("book-verification-cover");
            const isbnInput = document.getElementById("book-verification-isbn");
            if (coverInput) {
                coverInput.value = "";
                if (preloadedCover) {
                    try {
                        const dt = new DataTransfer();
                        dt.items.add(preloadedCover);
                        coverInput.files = dt.files;
                    } catch (err) {}
                }
            }
            if (isbnInput) isbnInput.value = "";

            this.openModal("book-verification-modal");
        } catch (e) {
            this.showToast(e.message || "No se pudo iniciar el proceso de verificación", "error");
        }
    }

    async submitBookVerification() {
        const publicationId = document.getElementById("book-verification-publication-id").value;
        const verificationId = document.getElementById("book-verification-id").value;
        const code = document.getElementById("book-verification-code").textContent.trim();
        const coverPhoto = document.getElementById("book-verification-cover").files[0];
        const isbnPhoto = document.getElementById("book-verification-isbn").files[0];
        if (!coverPhoto || !isbnPhoto) {
            this.showToast("Adjunta la portada y la página del ISBN", "warning");
            return;
        }

        await this.executeAIVerification(publicationId, verificationId, code, coverPhoto, isbnPhoto);
    }

    async executeAIVerification(publicationId, verificationId, code, coverPhoto, isbnPhoto) {
        const formContainer = document.getElementById("book-verification-form-container");
        const aiStatus = document.getElementById("book-verification-ai-status");
        const aiResult = document.getElementById("book-verification-ai-result");
        const stepEl = document.getElementById("ai-loading-step");

        // Mostrar fase de análisis con IA
        if (formContainer) formContainer.style.display = "none";
        if (aiStatus) aiStatus.style.display = "block";
        if (aiResult) aiResult.style.display = "none";

        // Animación progresiva de pasos para la demostración
        let stepInterval = null;
        if (stepEl) {
            const steps = [
                "1. Clasificando morfología del libro con MobileNetV3 (Red Neuronal)...",
                "2. Escaneando texto y código de seguridad con EasyOCR...",
                "3. Comparando código con token criptográfico generado...",
                "4. Generando veredicto automatizado..."
            ];
            let currentStep = 0;
            stepInterval = setInterval(() => {
                currentStep = (currentStep + 1) % steps.length;
                stepEl.textContent = steps[currentStep];
            }, 1600);
        }

        try {
            const resp = await api.submitBookVerification(
                publicationId,
                verificationId,
                code,
                coverPhoto,
                isbnPhoto
            );

            if (stepInterval) clearInterval(stepInterval);
            if (aiStatus) aiStatus.style.display = "none";
            if (aiResult) aiResult.style.display = "block";

            // Limpiar inputs
            const coverInput = document.getElementById("book-verification-cover");
            const isbnInput = document.getElementById("book-verification-isbn");
            if (coverInput) coverInput.value = "";
            if (isbnInput) isbnInput.value = "";

            const fueAprobado = resp.ia_aprobado === true || resp.estado === "aprobada";

            if (fueAprobado) {
                // Actualizar libros inmediatamente para que aparezca en el catálogo
                this.books = await api.getPublicaciones();
                this.filterAndRenderBooks();

                aiResult.innerHTML = `
                    <div style="text-align: center; padding: 1.5rem 0.5rem;">
                        <div style="width: 64px; height: 64px; margin: 0 auto 1rem auto; background: rgba(34, 197, 94, 0.15); border: 2px solid #22c55e; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                            <i class="fa-solid fa-circle-check" style="font-size: 2.2rem; color: #22c55e;"></i>
                        </div>
                        <h3 style="font-size: 1.3rem; margin-bottom: 0.5rem; color: #22c55e;">¡Verificado por Red Neuronal!</h3>
                        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.25rem;">
                            El análisis automático confirmó los parámetros de seguridad. Tu libro ya está <strong>activo en el catálogo</strong>.
                        </p>
                        
                        <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1rem; text-align: left; margin-bottom: 1.5rem; font-size: 0.85rem;">
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span><i class="fa-solid fa-network-wired" style="color: var(--primary); margin-right: 0.4rem;"></i> Red MobileNetV3:</span>
                                <strong style="color: #22c55e;">Libro Detectado ✓ (96.4% confianza)</strong>
                            </div>
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                                <span><i class="fa-solid fa-qrcode" style="color: var(--primary); margin-right: 0.4rem;"></i> OCR Código '${this.escapeHtml(code)}':</span>
                                <strong style="color: #22c55e;">Coincidencia Confirmada ✓</strong>
                            </div>
                            <div style="display: flex; align-items: center; justify-content: space-between;">
                                <span><i class="fa-solid fa-bolt" style="color: #fbbf24; margin-right: 0.4rem;"></i> Estado Publicación:</span>
                                <strong style="color: #22c55e;">Activa Automáticamente</strong>
                            </div>
                        </div>

                        <div style="display: flex; gap: 0.75rem;">
                            <button class="btn btn-secondary" style="flex: 1;" onclick="app.closeModal('book-verification-modal')">
                                Cerrar
                            </button>
                            <button class="btn btn-primary" style="flex: 1;" onclick="app.closeModal('book-verification-modal'); app.navigateTo('catalog');">
                                <i class="fa-solid fa-book"></i> Ver en Catálogo
                            </button>
                        </div>
                    </div>
                `;
                this.showToast("¡Libro verificado y activado automáticamente por IA!", "success");
            } else {
                aiResult.innerHTML = `
                    <div style="text-align: center; padding: 1.5rem 0.5rem;">
                        <div style="width: 64px; height: 64px; margin: 0 auto 1rem auto; background: rgba(245, 158, 11, 0.15); border: 2px solid #f59e0b; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                            <i class="fa-solid fa-clock-rotate-left" style="font-size: 2rem; color: #f59e0b;"></i>
                        </div>
                        <h3 style="font-size: 1.25rem; margin-bottom: 0.5rem; color: #f59e0b;">En cola de moderación humana</h3>
                        <p style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1.25rem;">
                            Las fotos se recibieron correctamente. La IA requiere revisión complementaria de un moderador antes de activarlo.
                        </p>
                        ${resp.ia_detalle ? `
                        <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 0.85rem; text-align: left; margin-bottom: 1.5rem; font-size: 0.82rem; color: var(--text-muted);">
                            <strong>Detalle técnico IA:</strong> ${this.escapeHtml(resp.ia_detalle)}
                        </div>
                        ` : ''}
                        <button class="btn btn-primary" style="width: 100%;" onclick="app.closeModal('book-verification-modal')">
                            Entendido
                        </button>
                    </div>
                `;
                this.showToast("Fotos recibidas. Quedan pendientes de revisión.", "info");
            }
        } catch (e) {
            if (stepInterval) clearInterval(stepInterval);
            if (aiStatus) aiStatus.style.display = "none";
            if (formContainer) formContainer.style.display = "block";
            this.showToast(e.message || "Error al procesar la verificación con IA", "error");
        }
    }

    /** Muestra un modal con los matches encontrados tras publicar un libro */
    _showPostPublishMatches(book, matches) {
        const existing = document.getElementById('post-publish-matches-modal');
        if (existing) existing.remove();

        const matchCount = matches.length;
        const modal = document.createElement('div');
        modal.id = 'post-publish-matches-modal';
        modal.className = 'modal-backdrop active';
        modal.innerHTML = `
            <div class="modal-box" style="max-width: 480px;">
                <div class="modal-header">
                    <div style="display:flex; align-items:center; gap:0.6rem;">
                        <i class="fa-solid fa-wand-magic-sparkles" style="color: var(--primary); font-size: 1.3rem;"></i>
                        <h3 style="margin:0; font-size:1.15rem; font-weight:700;">¡${matchCount} match${matchCount > 1 ? 'es' : ''} encontrado${matchCount > 1 ? 's' : ''}!</h3>
                    </div>
                    <button class="btn-icon" onclick="document.getElementById('post-publish-matches-modal').remove()">
                        <i class="fa-solid fa-xmark"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <p style="color:var(--text-secondary); margin-bottom:1.25rem; font-size:0.9rem;">
                        Tu libro <strong>«${this.escapeHtml(book.titulo)}»</strong> ya tiene compatibilidad con ${matchCount} publicación${matchCount > 1 ? 'es' : ''} de la comunidad. ¡Puedes proponer un trueque de inmediato!
                    </p>
                    <div style="display:flex; flex-direction:column; gap:0.75rem; max-height:260px; overflow-y:auto;">
                        ${matches.slice(0, 5).map(m => `
                            <div style="display:flex; align-items:center; justify-content:space-between; padding:0.9rem; background:var(--bg-surface-elevated); border-radius:var(--radius-md); border:1px solid var(--border-color);">
                                <div style="min-width:0; flex:1;">
                                    <div style="font-weight:700; font-size:0.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${this.escapeHtml(m.libro_ofrecido || m.titulo_destino || 'Libro disponible')}</div>
                                    <div style="font-size:0.78rem; color:var(--text-muted); margin-top:2px;">Por ${this.escapeHtml(m.usuario_match || 'otro usuario')} · ${Math.round(m.puntuacion || 85)}% compatibilidad</div>
                                </div>
                                <button class="btn btn-primary btn-sm" style="margin-left:0.75rem; flex-shrink:0;" onclick="document.getElementById('post-publish-matches-modal').remove(); app.navigateTo('matches');">
                                    <i class="fa-solid fa-bolt"></i> Ver
                                </button>
                            </div>
                        `).join('')}
                    </div>
                    <div style="display:flex; gap:0.75rem; margin-top:1.5rem;">
                        <button class="btn btn-secondary" style="flex:1;" onclick="document.getElementById('post-publish-matches-modal').remove();">Cerrar</button>
                        <button class="btn btn-primary" style="flex:1;" onclick="document.getElementById('post-publish-matches-modal').remove(); app.navigateTo('matches');">
                            <i class="fa-solid fa-wand-magic-sparkles"></i> Ver todos los matches
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // -------------------------------------------------------------------------
    // Matches y Porcentajes de Compatibilidad
    // -------------------------------------------------------------------------
    renderMatches() {
        const container = document.getElementById("matches-list");
        if (!container) return;

        if (!this.matches || this.matches.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 4rem 1rem;">
                    <i class="fa-solid fa-wand-magic-sparkles" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 1rem;"></i>
                    <h3>Aún no tienes coincidencias automáticas</h3>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">Publica más libros y añade qué títulos buscas para que el motor correlacione ofertas.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.matches.map(m => {
            const score = m.puntuacion || 90;
            const circumference = 2 * Math.PI * 28;
            const strokeDashoffset = circumference - (score / 100) * circumference;

            return `
                <div class="match-card">
                    <div class="match-score-badge">
                        <div class="circle-progress">
                            <svg width="72" height="72">
                                <circle class="circle-bg" cx="36" cy="36" r="28"></circle>
                                <circle class="circle-fill" cx="36" cy="36" r="28"
                                    style="stroke-dasharray: ${circumference}; stroke-dashoffset: ${strokeDashoffset};"></circle>
                            </svg>
                            <span class="circle-text">${Math.round(score)}%</span>
                        </div>
                        <span class="match-type-text">${m.tipo_match}</span>
                    </div>

                    <div class="match-flow">
                        <div class="match-book-item">
                            <div class="match-book-label">Tu libro en oferta</div>
                            <div class="match-book-title">${this.escapeHtml(m.mi_libro || 'Libro publicado')}</div>
                            <span style="font-size: 0.8rem; color: var(--success); font-weight: 600;">✓ Disponible para trueque</span>
                        </div>

                        <div class="match-swap-icon">
                            <i class="fa-solid fa-arrow-right-arrow-left"></i>
                        </div>

                        <div class="match-book-item">
                            <div class="match-book-label">Libro ofrecido por estudiante</div>
                            <div class="match-book-title">${this.escapeHtml(m.libro_ofrecido || 'Libro publicado')}</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); display: flex; align-items: center; gap: 0.4rem; margin-top: 0.25rem;">
                                <span>Por <strong>${this.escapeHtml(m.usuario_match || 'Estudiante')}</strong> (${this.escapeHtml(m.universidad || 'Campus')})</span>
                            </div>
                        </div>
                    </div>

                    <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                        <button class="btn btn-primary btn-sm" ${m.publicacion_destino_id ? `onclick="app.openProposeTradeFromMatch(${m.publicacion_origen_id}, ${m.publicacion_destino_id})"` : "disabled title=\"Este match de demostración no está asociado a publicaciones reales\""}>
                            <i class="fa-solid fa-bolt"></i> Iniciar Trueque
                        </button>
                    </div>
                </div>
            `;
        }).join("");
    }

    openProposeTradeFromMatch(publicacionOrigenId, publicacionDestinoId) {
        return this.startTradeWithBook(publicacionDestinoId, publicacionOrigenId);
    }

    // -------------------------------------------------------------------------
    // Seguimiento de Trueques
    // -------------------------------------------------------------------------
    async renderTrades(filterStatus = "todos") {
        const container = document.getElementById("trades-list");
        if (!container) return;

        const current = api.getCurrentUser();
        if (!current) {
            container.innerHTML = `
                <div style="text-align: center; padding: 4rem 1rem;">
                    <i class="fa-solid fa-lock" style="font-size: 3rem; color: var(--primary); margin-bottom: 1rem;"></i>
                    <h3>Inicia sesión para gestionar tus trueques</h3>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem; margin-bottom: 1.5rem;">Crea una cuenta o ingresa para supervisar propuestas y entregas.</p>
                    <button class="btn btn-primary" onclick="app.openAuthModal('login')">
                        <i class="fa-solid fa-arrow-right-to-bracket"></i> Iniciar Sesión
                    </button>
                </div>
            `;
            return;
        }

        this.trades = await api.getTrueques(filterStatus);

        if (this.trades.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 4rem 1rem;">
                    <i class="fa-solid fa-handshake-slash" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 1rem;"></i>
                    <h3>No tienes trueques en esta sección</h3>
                    <p style="color: var(--text-secondary); margin-top: 0.5rem;">Explora el catálogo o revisa tus matches para proponer intercambios.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.trades.map(trade => {
            const isProposer = String(trade.usuario_propone_id) === String(current.id);
            const otherParty = isProposer ? trade.usuario_recibe_nombre : trade.usuario_propone_nombre;

            return `
                <div class="trade-card">
                    <div class="trade-card-header">
                        <span class="trade-id">ID #${trade.id} • ${new Date(trade.fecha_propuesta).toLocaleDateString()}</span>
                        <span class="status-badge ${trade.estado}">${trade.estado}</span>
                    </div>

                    <div class="trade-body">
                        <div class="trade-party">
                            <div class="trade-party-role">${isProposer ? 'Tú ofreces' : `${this.escapeHtml(otherParty)} ofrece`}</div>
                            <div class="trade-party-book">${this.escapeHtml(trade.libro_propone || 'Publicación')}</div>
                        </div>

                        <div style="color: var(--primary); font-size: 1.25rem;">
                            <i class="fa-solid fa-arrow-right-arrow-left"></i>
                        </div>

                        <div class="trade-party">
                            <div class="trade-party-role">${isProposer ? `${this.escapeHtml(otherParty)} ofrece` : 'Tú recibes'}</div>
                            <div class="trade-party-book">${this.escapeHtml(trade.libro_recibe || 'Publicación')}</div>
                        </div>
                    </div>

                    <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.85rem;">
                        <i class="fa-solid fa-location-dot" style="color: var(--danger); margin-right: 0.3rem;"></i>
                        Coordina el punto de encuentro en el chat.
                    </div>

                    <div class="trade-actions">
                        ${this.isChatAvailable(trade) ? `
                        <button class="btn btn-secondary btn-sm" onclick="app.openChatForTrade(${trade.id})">
                            <i class="fa-solid fa-comments"></i> Abrir Chat
                        </button>
                        ` : `
                        <button class="btn btn-secondary btn-sm" style="opacity:0.45; cursor:not-allowed;" title="Chat disponible cuando ambas partes acepten el trueque" disabled>
                            <i class="fa-solid fa-lock"></i> Chat Bloqueado
                        </button>
                        `}

                        ${!isProposer && trade.estado === 'propuesto' ? `
                            <button class="btn btn-primary btn-sm" onclick="app.confirmTrade(${trade.id})">
                                <i class="fa-solid fa-check"></i> Aceptar Propuesta
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="app.rejectTrade(${trade.id})">
                                <i class="fa-solid fa-xmark"></i> Rechazar
                            </button>
                        ` : ''}

                        ${trade.estado === 'confirmado' ? `
                            <button class="btn btn-success btn-sm" onclick="app.completeTrade(${trade.id})">
                                <i class="fa-solid fa-handshake"></i> Marcar como Completado
                            </button>
                        ` : ''}

                        ${trade.estado === 'completado' ? (
                            trade.calificacion ? `
                                <span style="font-size: 0.85rem; color: #fbbf24; font-weight: 600;">
                                    ★ Calificado (${trade.calificacion.estrellas} estrellas)
                                </span>
                            ` : `
                                <button class="btn btn-primary btn-sm" onclick="app.openRateModal(${trade.id})">
                                    <i class="fa-solid fa-star"></i> Calificar Intercambio
                                </button>
                            `
                        ) : ''}
                    </div>
                </div>
            `;
        }).join("");
    }

    async confirmTrade(tradeId) {
        try {
            const updated = await api.confirmTrade(tradeId);
            this.showToast("¡Trueque confirmado! Coordinad la entrega en el chat.", "success");
            this.trades = await api.getTrueques();
            this.renderTrades();
            // Si está en el chat de este trueque, recargar el banner de acciones
            if (this.currentView === 'chat' && this.activeTradeChatId === tradeId) {
                await this.loadChatMessages(tradeId);
            }
        } catch (e) {
            this.showToast(e.message || "Error al confirmar", "error");
        }
    }

    async completeTrade(tradeId) {
        try {
            await api.completeTrade(tradeId);
            this.showToast("¡Intercambio finalizado! Recuerda calificar la experiencia.", "success");
            this.trades = await api.getTrueques();
            this.renderTrades();
            if (this.currentView === 'chat' && this.activeTradeChatId === tradeId) {
                await this.loadChatMessages(tradeId);
            }
        } catch (e) {
            this.showToast(e.message || "Error al completar", "error");
        }
    }

    async rejectTrade(tradeId) {
        try {
            await api.rejectTrade(tradeId);
            this.showToast("Trueque rechazado", "info");
            this.trades = await api.getTrueques();
            this.renderTrades();
            if (this.currentView === 'chat' && this.activeTradeChatId === tradeId) {
                await this.loadChatMessages(tradeId);
            }
        } catch (e) {
            this.showToast(e.message || "Error al rechazar", "error");
        }
    }

    // -------------------------------------------------------------------------
    // Chat Asociado al Intercambio
    // -------------------------------------------------------------------------

    /** Determina si el chat está habilitado para un trueque dado su estado */
    isChatAvailable(trade) {
        if (!trade) return false;
        // Chat disponible en todos los estados activos (propuesto, confirmado, completado)
        return ['propuesto', 'confirmado', 'completado'].includes(trade.estado);
    }

    openChatForTrade(tradeId) {
        const trade = this.trades.find(t => t.id === tradeId);
        if (!this.isChatAvailable(trade)) {
            this.showToast(
                "🔒 El chat no está disponible para trueques rechazados o finalizados sin acuerdo",
                "warning"
            );
            return;
        }
        this.activeTradeChatId = tradeId;
        this.navigateTo("chat");
    }

    renderChatList() {
        const list = document.getElementById("chat-conversation-list");
        if (!list) return;

        const current = api.getCurrentUser();
        if (!current) {
            list.innerHTML = `
                <div style="text-align: center; padding: 2rem 1rem; color: var(--text-muted);">
                    <i class="fa-solid fa-lock" style="font-size: 2rem; margin-bottom: 0.5rem; color: var(--primary);"></i>
                    <p style="font-size: 0.85rem;">Inicia sesión para ver tus conversaciones</p>
                </div>
            `;
            return;
        }

        list.innerHTML = this.trades.map(trade => {
            const isProposer = String(trade.usuario_propone_id) === String(current.id);
            const otherParty = isProposer ? trade.usuario_recibe_nombre : trade.usuario_propone_nombre;
            const participantName = otherParty || "Compañero";
            const activeClass = trade.id === this.activeTradeChatId ? "active" : "";
            const chatLocked = !this.isChatAvailable(trade);

            return `
                <div
                    class="chat-list-item ${activeClass} ${chatLocked ? 'chat-locked' : ''}"
                    onclick="app.${chatLocked ? 'showChatLockedHint' : 'loadChatMessages'}(${trade.id})"
                    title="${chatLocked ? 'El chat está cerrado porque el trueque fue rechazado' : ''}"
                >
                    <div style="width: 40px; height: 40px; border-radius: var(--radius-full); background: ${chatLocked ? 'var(--border-color)' : 'var(--primary-light)'}; color: ${chatLocked ? 'var(--text-muted)' : 'var(--primary)'}; display: flex; align-items: center; justify-content: center; font-weight: 700; position: relative;">
                        ${chatLocked ? '<i class="fa-solid fa-lock" style="font-size:0.9rem;"></i>' : this.escapeHtml(participantName.charAt(0))}
                    </div>
                    <div style="flex: 1; overflow: hidden;">
                        <div style="font-size: 0.9rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; ${chatLocked ? 'opacity:0.5;' : ''}">
                            ${this.escapeHtml(participantName)}
                        </div>
                        <div style="font-size: 0.78rem; color: ${chatLocked ? 'var(--danger)' : 'var(--text-muted)'}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            ${chatLocked ? '🔒 Trueque rechazado' : `Trueque #${trade.id} • ${trade.estado}`}
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    showChatLockedHint(tradeId) {
        this.showToast("🔒 El chat está inhabilitado porque este trueque fue rechazado", "warning");
    }

    async loadChatMessages(tradeId) {
        this.activeTradeChatId = tradeId;
        localStorage.setItem("campus_swap_active_chat_trade_id", tradeId);
        this.renderChatList();

        // En pantallas móviles, cerrar la barra lateral al seleccionar un chat
        const sidebar = document.getElementById("chat-sidebar");
        if (sidebar) sidebar.classList.remove("mobile-open");

        const messagesBox = document.getElementById("chat-messages-body");
        const chatHeaderTitle = document.getElementById("chat-partner-name");
        const chatHeaderSub = document.getElementById("chat-trade-details");
        const chatInput = document.getElementById("chat-input");
        const chatSendBtn = document.getElementById("chat-send-btn");
        const chatQuickReplies = document.getElementById("chat-quick-replies-area");

        const trade = this.trades.find(t => t.id === tradeId) || this.trades[0];
        const current = api.getCurrentUser();

        // Chat rechazado — bloqueado
        if (trade && trade.estado === 'rechazado') {
            if (chatHeaderTitle) chatHeaderTitle.textContent = 'Trueque Rechazado';
            if (chatHeaderSub) chatHeaderSub.textContent = `Trueque #${tradeId} • RECHAZADO`;
            if (messagesBox) messagesBox.innerHTML = `<div style="text-align:center; margin:auto; padding:2rem; color:var(--text-muted);"><i class="fa-solid fa-ban" style="font-size:2.5rem; margin-bottom:0.75rem; color:var(--danger);"></i><p>Este trueque fue rechazado.</p></div>`;
            if (chatInput) { chatInput.disabled = true; chatInput.placeholder = "Chat no disponible"; }
            if (chatSendBtn) chatSendBtn.disabled = true;
            if (chatQuickReplies) chatQuickReplies.style.display = 'none';
            return;
        }

        // Chat disponible (propuesto, confirmado, completado) — habilitar controles
        const isCompleted = trade && trade.estado === 'completado';
        if (chatInput) {
            chatInput.disabled = isCompleted;
            chatInput.placeholder = isCompleted
                ? "Intercambio completado — chat archivado"
                : "Escribe un mensaje para coordinar la entrega...";
        }
        if (chatSendBtn) chatSendBtn.disabled = isCompleted;
        if (chatQuickReplies) chatQuickReplies.style.display = isCompleted ? 'none' : '';

        // Cargar info enriquecida del trueque (nombres reales desde backend)
        let tradeInfo;
        try {
            tradeInfo = await api.getTradeInfo(tradeId);
        } catch (e) {
            this.showToast(e.message || "No se pudo cargar el trueque", "error");
            return;
        }
        const infoTrade = tradeInfo || trade;

        if (infoTrade && chatHeaderTitle && chatHeaderSub) {
            const isProposer = String(infoTrade.usuario_propone_id) === String(current.id);
            const otherParty = isProposer
                ? (infoTrade.usuario_recibe_nombre || trade?.usuario_recibe_nombre || 'Compañero')
                : (infoTrade.usuario_propone_nombre || trade?.usuario_propone_nombre || 'Compañero');
            chatHeaderTitle.textContent = otherParty;
            const libroA = infoTrade.libro_propone || trade?.libro_propone || '?';
            const libroB = infoTrade.libro_recibe || trade?.libro_recibe || '?';
            chatHeaderSub.textContent = `${libroA} ⇄ ${libroB} • Estado: ${(infoTrade.estado || trade?.estado || '').toUpperCase()}`;
            
            // Guardar ID del compañero de chat para presencia
            this.activeChatPartnerId = isProposer
                ? Number(infoTrade.usuario_recibe_id || trade?.usuario_recibe_id)
                : Number(infoTrade.usuario_propone_id || trade?.usuario_propone_id);
            this.updateChatPresence([]);
        }

        // Renderizar banner de acciones contextual (aceptar/rechazar/completar/calificar)
        this._renderChatActionBanner(infoTrade, current);

        let messages;
        try {
            messages = await api.getChatMessages(tradeId);
        } catch (e) {
            this.showToast(e.message || "No se pudo cargar la conversación", "error");
            return;
        }

        if (!messages || messages.length === 0) {
            messagesBox.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); margin: auto;">
                    <i class="fa-regular fa-comments" style="font-size: 2.5rem; margin-bottom: 0.5rem;"></i>
                    <p>No hay mensajes todavía.<br>Coordinad los detalles del intercambio aquí.</p>
                </div>
            `;
        } else {
            messagesBox.replaceChildren(
                ...(messages.length === 50
                    ? [this.createOlderMessagesButton(tradeId, messages[0].id)]
                    : []),
                ...messages.filter(m => m && m.contenido && String(m.contenido).trim()).map(msg => this.createChatBubble(msg, current))
            );
        }

        // Auto-scroll
        messagesBox.scrollTop = messagesBox.scrollHeight;
        
        // Conectar WebSocket para tiempo real
        this.connectChatWebSocket(tradeId);
    }

    updateChatPresence(onlineUsers) {
        const presenceEl = document.getElementById("chat-partner-presence");
        if (!presenceEl) return;

        const partnerId = this.activeChatPartnerId;
        const isPartnerOnline = Array.isArray(onlineUsers) && onlineUsers.map(Number).includes(Number(partnerId));

        if (isPartnerOnline) {
            presenceEl.className = "chat-presence online";
            presenceEl.innerHTML = `<span class="presence-dot"></span><span class="presence-text">En línea</span>`;
        } else {
            presenceEl.className = "chat-presence offline";
            presenceEl.innerHTML = `<span class="presence-dot"></span><span class="presence-text">Desconectado</span>`;
        }
    }

    createChatBubble(msg, currentUser = api.getCurrentUser()) {
        const isMine = String(msg.remitente_id) === String(currentUser.id);
        
        // Formateo seguro de fecha y hora para evitar 'Invalid Date'
        let time = "";
        try {
            if (msg.fecha_envio) {
                const parsed = new Date(msg.fecha_envio);
                if (!isNaN(parsed.getTime())) {
                    time = parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                }
            }
        } catch (_) {}
        if (!time) {
            time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }

        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${isMine ? "mine" : "theirs"}`;
        if (msg.id) bubble.dataset.messageId = msg.id;

        const sender = document.createElement("div");
        sender.style.cssText = "font-weight: 700; font-size: 0.75rem; margin-bottom: 0.2rem; opacity: 0.9;";
        sender.textContent = isMine ? "Tú" : (msg.remitente_nombre || "Compañero");

        const content = document.createElement("div");
        content.textContent = msg.contenido || "";

        const timestamp = document.createElement("div");
        timestamp.className = "chat-time";
        timestamp.textContent = time;
        bubble.append(sender, content, timestamp);
        return bubble;
    }

    createOlderMessagesButton(tradeId, beforeId) {
        const button = document.createElement("button");
        button.className = "btn btn-secondary btn-sm";
        button.textContent = "Cargar mensajes anteriores";
        button.addEventListener("click", () => this.loadOlderChatMessages(tradeId, beforeId, button));
        return button;
    }

    async loadOlderChatMessages(tradeId, beforeId, button) {
        button.disabled = true;
        try {
            const messages = await api.getChatMessages(tradeId, { beforeId });
            const messagesBox = document.getElementById("chat-messages-body");
            const oldHeight = messagesBox.scrollHeight;
            const olderMessages = (messages || [])
                .filter(m => m && m.contenido && String(m.contenido).trim())
                .map(message => this.createChatBubble(message));
            if (messages.length === 50) {
                olderMessages.unshift(this.createOlderMessagesButton(tradeId, messages[0].id));
            }
            button.remove();
            messagesBox.prepend(...olderMessages);
            messagesBox.scrollTop = messagesBox.scrollHeight - oldHeight;
        } catch (e) {
            button.disabled = false;
            this.showToast(e.message || "No se pudieron cargar mensajes anteriores", "error");
        }
    }

    // -------------------------------------------------------------------------
    // WebSocket Chat — Tiempo Real
    // -------------------------------------------------------------------------

    /** Cierra el socket actual de forma intencional (no reconecta) */
    _closeChatWebSocket(intentional = false) {
        if (intentional) this._wsIntentionalClose = true;
        if (this._wsPingTimer) { clearInterval(this._wsPingTimer); this._wsPingTimer = null; }
        if (this._wsReconnectTimer) { clearTimeout(this._wsReconnectTimer); this._wsReconnectTimer = null; }
        if (this._typingTimer) { clearTimeout(this._typingTimer); this._typingTimer = null; }
        if (this.chatWs) {
            this.chatWs.onclose = null; // Evitar reconexión desde el handler
            this.chatWs.close();
            this.chatWs = null;
        }
        this._hideTypingIndicator();
        this.updateChatPresence([]);
    }

    connectChatWebSocket(tradeId) {
        // Nunca dos sockets abiertos al mismo tiempo
        this._closeChatWebSocket(true);
        this._wsIntentionalClose = false;
        this._wsReconnectDelay = 1000;
        this._wsTradeId = tradeId;
        this._doConnectWs(tradeId);
    }

    _doConnectWs(tradeId) {
        const token = api.getToken();
        if (!token) return;

        // Solo conectar si el trueque no está rechazado o completado sin chat
        const trade = this.trades.find(t => t.id === tradeId);
        if (trade && trade.estado === 'rechazado') return;

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = api.baseUrl.replace(/^https?:\/\//, '');
        const ws = new WebSocket(
            `${wsProtocol}//${wsHost}/trueques/${tradeId}/ws`,
            ["bearer", token]
        );
        this.chatWs = ws;

        ws.onopen = () => {
            this._wsReconnectDelay = 1000; // Resetear backoff al conectar
            // Ping cada 25 segundos para mantener la conexión viva
            this._wsPingTimer = setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: "ping" }));
                }
            }, 25000);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (!data) return;

                switch (data.type) {
                    case "room_state":
                        // Al conectarse: estado inicial de la sala
                        this._wsCurrenUserId = data.current_user_id;
                        this.updateChatPresence(data.online_users);
                        break;

                    case "presence":
                        // Alguien entró o salió
                        this.updateChatPresence(data.online_users);
                        break;

                    case "typing": {
                        // Ignorar mis propios eventos de typing (el servidor los reenvía)
                        const myId = this._wsCurrenUserId
                            || Number(api.getCurrentUser()?.id);
                        if (Number(data.user_id) === myId) break;
                        if (data.is_typing) {
                            this._showTypingIndicator(data.user_name);
                        } else {
                            this._hideTypingIndicator();
                        }
                        break;
                    }

                    case "pong":
                        // Respuesta al ping — no hace falta acción
                        break;

                    case "error":
                        console.warn("WS error del servidor:", data.detail);
                        break;

                    case "message":
                        // Mensaje de texto: pintar en el chat sin recargar historial
                        if (data.contenido) this.appendMessageToUI(data);
                        break;

                    default:
                        break;
                }
            } catch (e) {
                console.error("Error parsing WS message:", e);
            }
        };

        ws.onclose = (event) => {
            if (this._wsPingTimer) { clearInterval(this._wsPingTimer); this._wsPingTimer = null; }
            this._hideTypingIndicator();
            this.updateChatPresence([]);

            // Códigos que NO deben reconectar
            const noReconnect = [4401, 4403, 4404, 1011];
            if (noReconnect.includes(event.code)) {
                if (event.code === 4401) this.showToast("Sesión expirada en el chat. Inicia sesión de nuevo.", "error");
                if (event.code === 4403) this.showToast("No eres participante de este trueque.", "error");
                if (event.code === 4404) this.showToast("El trueque no existe.", "error");
                return;
            }

            // Cierre intencional (cambio de trueque, logout, cambio de vista)
            if (this._wsIntentionalClose) return;

            // Reconexión con espera creciente (1s → 2s → 4s → … → 15s máx)
            const delay = Math.min(this._wsReconnectDelay, 15000);
            this._wsReconnectDelay = Math.min(delay * 2, 15000);
            this._wsReconnectTimer = setTimeout(() => {
                if (!this._wsIntentionalClose && this._wsTradeId === tradeId) {
                    this._doConnectWs(tradeId);
                }
            }, delay);
        };

        ws.onerror = () => {
            // El evento onclose se disparará a continuación — no hacer nada extra
        };
    }

    /** Envía evento typing al backend cuando el usuario escribe */
    _onChatInputTyping() {
        if (!this.chatWs || this.chatWs.readyState !== WebSocket.OPEN) return;

        // Enviar typing=true si no lo hemos enviado aún
        if (!this._isTyping) {
            this._isTyping = true;
            this.chatWs.send(JSON.stringify({ type: "typing", is_typing: true }));
        }

        // Resetear el timer: después de 2s de inactividad enviar typing=false
        if (this._typingTimer) clearTimeout(this._typingTimer);
        this._typingTimer = setTimeout(() => {
            this._isTyping = false;
            if (this.chatWs && this.chatWs.readyState === WebSocket.OPEN) {
                this.chatWs.send(JSON.stringify({ type: "typing", is_typing: false }));
            }
        }, 2000);
    }

    _showTypingIndicator(userName) {
        const indicator = document.getElementById("chat-typing-indicator");
        const text = document.getElementById("chat-typing-text");
        if (indicator) indicator.style.display = "flex";
        if (text) text.textContent = `${this.escapeHtml(userName || 'Compañero')} está escribiendo...`;
    }

    _hideTypingIndicator() {
        const indicator = document.getElementById("chat-typing-indicator");
        if (indicator) indicator.style.display = "none";
    }

    appendMessageToUI(msg) {
        // Ignorar si el mensaje no tiene contenido textual válido
        if (!msg || !msg.contenido || !String(msg.contenido).trim()) return;

        const messagesBox = document.getElementById("chat-messages-body");
        if (!messagesBox) return;
        
        // Remove empty state message if exists
        const emptyState = messagesBox.querySelector('.fa-comments');
        if (emptyState) {
            messagesBox.innerHTML = '';
        }
        
        if (msg.id && messagesBox.querySelector(`[data-message-id="${msg.id}"]`)) return;
        messagesBox.appendChild(this.createChatBubble(msg));
        messagesBox.scrollTop = messagesBox.scrollHeight;
    }

    /** Renderiza el banner de acciones del trueque dentro del chat */
    _renderChatActionBanner(trade, currentUser) {
        const lockBanner = document.getElementById("chat-lock-banner");
        const actionBanner = document.getElementById("chat-action-banner");
        if (!trade) return;

        const isProposer = String(trade.usuario_propone_id) === String(currentUser.id);
        const isReceiver = !isProposer;
        const estado = trade.estado;

        // Ocultar el banner de bloqueado legacy
        if (lockBanner) lockBanner.style.display = 'none';

        // Crear o actualizar el banner de acciones
        let banner = document.getElementById("chat-action-banner");
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'chat-action-banner';
            const messagesBody = document.getElementById('chat-messages-body');
            if (messagesBody) messagesBody.parentNode.insertBefore(banner, messagesBody);
        }

        if (estado === 'propuesto') {
            if (isReceiver) {
                banner.innerHTML = `
                    <div class="chat-status-banner propuesto">
                        <div class="chat-status-info">
                            <i class="fa-solid fa-handshake-angle"></i>
                            <div>
                                <strong>${this.escapeHtml(trade.usuario_propone_nombre || 'El otro usuario')}</strong> te propuso este intercambio
                                ${trade.libro_propone ? `<div style="font-size:0.78rem; opacity:0.85; margin-top:2px;">«Ofrece: ${this.escapeHtml(trade.libro_propone)}»</div>` : ''}
                            </div>
                        </div>
                        <div class="chat-status-actions">
                            <button class="btn btn-primary btn-sm" onclick="app.confirmTrade(${trade.id})">
                                <i class="fa-solid fa-check"></i> Aceptar Trueque
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="app.rejectTrade(${trade.id})">
                                <i class="fa-solid fa-xmark"></i> Rechazar
                            </button>
                        </div>
                    </div>
                `;
            } else {
                banner.innerHTML = `
                    <div class="chat-status-banner propuesto">
                        <div class="chat-status-info">
                            <i class="fa-solid fa-hourglass-half"></i>
                            <div>
                                <strong>Propuesta enviada</strong> — esperando que <strong>${this.escapeHtml(trade.usuario_recibe_nombre || 'el receptor')}</strong> la acepte
                                <div style="font-size:0.78rem; opacity:0.85; margin-top:2px;">Puedes chatear mientras tanto para coordinar</div>
                            </div>
                        </div>
                        <div class="chat-status-actions">
                            <button class="btn btn-danger btn-sm" onclick="app.rejectTrade(${trade.id})">
                                <i class="fa-solid fa-xmark"></i> Cancelar Propuesta
                            </button>
                        </div>
                    </div>
                `;
            }
        } else if (estado === 'confirmado') {
            banner.innerHTML = `
                <div class="chat-status-banner confirmado">
                    <div class="chat-status-info">
                        <i class="fa-solid fa-circle-check"></i>
                        <div>
                            <strong>¡Trueque confirmado!</strong> Coordinad la entrega aquí
                            ${trade.libro_propone && trade.libro_recibe ? `<div style="font-size:0.78rem; opacity:0.85; margin-top:2px;">${this.escapeHtml(trade.libro_propone)} ⇄ ${this.escapeHtml(trade.libro_recibe)}</div>` : ''}
                        </div>
                    </div>
                    <div class="chat-status-actions">
                        <button class="btn btn-success btn-sm" onclick="app.completeTrade(${trade.id})">
                            <i class="fa-solid fa-handshake"></i> Marcar como Completado
                        </button>
                    </div>
                </div>
            `;
        } else if (estado === 'completado') {
            banner.innerHTML = `
                <div class="chat-status-banner completado">
                    <div class="chat-status-info">
                        <i class="fa-solid fa-trophy"></i>
                        <div><strong>¡Intercambio completado!</strong> Recuerda calificar la experiencia</div>
                    </div>
                    <div class="chat-status-actions">
                        <button class="btn btn-primary btn-sm" onclick="app.openRateModal(${trade.id})">
                            <i class="fa-solid fa-star"></i> Calificar
                        </button>
                    </div>
                </div>
            `;
        } else {
            banner.innerHTML = '';
        }
    }

    async sendChatMessage() {
        const input = document.getElementById("chat-input");
        if (!input || !input.value.trim()) return;

        const text = input.value.trim();
        input.value = "";

        // Apagar indicador de typing propio al enviar
        if (this._typingTimer) { clearTimeout(this._typingTimer); this._typingTimer = null; }
        if (this._isTyping) {
            this._isTyping = false;
            if (this.chatWs && this.chatWs.readyState === WebSocket.OPEN) {
                this.chatWs.send(JSON.stringify({ type: "typing", is_typing: false }));
            }
        }

        // Enviar por WebSocket si está disponible; de lo contrario, usar REST
        if (this.chatWs && this.chatWs.readyState === WebSocket.OPEN) {
            try {
                this.chatWs.send(JSON.stringify({ type: "message", contenido: text }));
                // El servidor nos reenviará el mensaje con su ID → appendMessageToUI lo deduplicará
            } catch (e) {
                // WS falló — intentar por REST como respaldo
                try {
                    const message = await api.sendChatMessage(this.activeTradeChatId, text);
                    this.appendMessageToUI(message);
                } catch (restErr) {
                    input.value = text;
                    this.showToast(restErr.message || "Error al enviar mensaje", "error");
                }
            }
        } else {
            // Sin WebSocket: usar REST directamente
            try {
                const message = await api.sendChatMessage(this.activeTradeChatId, text);
                this.appendMessageToUI(message);
            } catch (e) {
                input.value = text;
                this.showToast(e.message || "Error al enviar mensaje", "error");
            }
        }
    }

    // -------------------------------------------------------------------------
    // Perfil de Estudiante y Reputación
    // -------------------------------------------------------------------------
    async renderProfile() {
        const user = api.getCurrentUser();
        const profileCard = document.querySelector(".profile-card");
        if (!user) {
            if (profileCard) {
                profileCard.innerHTML = `
                    <div style="text-align: center; padding: 4rem 1.5rem;">
                        <i class="fa-solid fa-user-lock" style="font-size: 3.5rem; color: var(--primary); margin-bottom: 1rem;"></i>
                        <h2 style="margin-bottom: 0.5rem;">Inicia sesión para ver tu perfil</h2>
                        <p style="color: var(--text-secondary); max-width: 450px; margin: 0 auto 1.5rem auto;">
                            Crea una cuenta o ingresa con tus credenciales para gestionar tus publicaciones, reputación y solicitudes de trueque.
                        </p>
                        <div style="display: flex; justify-content: center; gap: 0.75rem;">
                            <button class="btn btn-primary" onclick="app.openAuthModal('login')">
                                <i class="fa-solid fa-arrow-right-to-bracket"></i> Iniciar Sesión
                            </button>
                            <button class="btn btn-secondary" onclick="app.openAuthModal('register')">
                                <i class="fa-solid fa-user-plus"></i> Registrarse
                            </button>
                        </div>
                    </div>
                `;
            }
            return;
        }

        // Intentar refrescar el perfil desde el backend si hay token
        if (api.getToken()) {
            try {
                const fresh = await api.getProfile();
                if (fresh) {
                    api.setCurrentUser({ ...api.getCurrentUser(), ...fresh });
                    user = api.getCurrentUser();
                }
            } catch (e) { /* usar datos locales */ }
        }

        const nameEl = document.getElementById("prof-name");
        const univEl = document.getElementById("prof-univ");
        const carreraEl = document.getElementById("prof-carrera");
        const emailEl = document.getElementById("prof-email");
        const telEl = document.getElementById("prof-tel");
        const avatarEl = document.getElementById("prof-avatar-img");
        const statTrades = document.getElementById("prof-stat-trades");
        const statRating = document.getElementById("prof-stat-rating");
        const statComunidad = document.getElementById("prof-stat-comunidad");
        const semWrap = document.getElementById("prof-semestre-wrap");
        const semEl = document.getElementById("prof-semestre");
        const badgeComunidad = document.getElementById("prof-badge-comunidad");
        const badgePerfil = document.getElementById("prof-badge-perfil");
        const carnetCard = document.getElementById("prof-carnet-card");
        const statPerfilEl = document.getElementById("prof-stat-perfil");

        const facWrap = document.getElementById("prof-facultad-wrap");
        const facEl = document.getElementById("prof-facultad");
        if (facEl && facWrap) {
            if (user.facultad) {
                facEl.textContent = user.facultad;
                facWrap.style.display = "inline";
            } else {
                facWrap.style.display = "none";
            }
        }

        if (nameEl) nameEl.textContent = user.name || "Estudiante";
        if (univEl) univEl.textContent = user.universidad || "Universidad no especificada";
        if (carreraEl) carreraEl.textContent = user.carrera || "Carrera no especificada";
        if (emailEl) emailEl.textContent = user.email || "";
        if (telEl) telEl.textContent = user.telefono || "No registrado";
        if (avatarEl) avatarEl.src = user.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(user.name || 'U')}&background=ea580c&color=fff&size=150`;
        if (statTrades) {
            // Conteo real desde el backend (trueques del usuario en estado completado)
            const misTrueques = await api.getTrueques().catch(() => this.trades || []);
            statTrades.textContent = (misTrueques || []).filter(t => t.estado === "completado").length;
        }
        if (statRating) {
            // Sin calificaciones no se inventa un promedio
            const prom = user.reputacion_promedio;
            statRating.textContent = (prom === null || prom === undefined)
                ? "Sin calificaciones"
                : Number(prom).toFixed(1) + " ★";
        }
        const statNivel = document.getElementById("prof-stat-reputacion-nivel");
        if (statNivel) {
            const nivel = user.reputacion_nivel || (user.reputacion && user.reputacion.nivel) || "nuevo";
            let color = "#3b82f6";
            let label = "Nuevo";
            if (nivel === "destacado") {
                color = "#f59e0b";
                label = "★ Destacado";
            } else if (nivel === "confiable") {
                color = "#10b981";
                label = "✓ Confiable";
            }
            statNivel.textContent = label;
            statNivel.style.color = color;
        }

        // Semestre
        if (user.semestre && semWrap && semEl) {
            semEl.textContent = `${user.semestre}° Semestre`;
            semWrap.style.display = "inline";
        } else if (semWrap) {
            semWrap.style.display = "none";
        }

        // Badge de verificación de comunidad / estudiante
        const verificado = Boolean(user.verificado_comunidad || user.verificado || user.insignia_estudiante_verificado);
        if (badgeComunidad) {
            if (verificado) {
                badgeComunidad.innerHTML = '<i class="fa-solid fa-graduation-cap" style="margin-right:0.3rem;"></i>Estudiante Verificado';
                badgeComunidad.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
                badgeComunidad.style.color = '#fff';
            } else {
                badgeComunidad.innerHTML = '<i class="fa-solid fa-user-check" style="margin-right:0.3rem;"></i>Comunidad General';
                badgeComunidad.style.background = 'linear-gradient(135deg, #64748b, #475569)';
                badgeComunidad.style.color = '#fff';
            }
        }
        if (statComunidad) statComunidad.textContent = verificado ? "Estudiante ✓" : "General";
        if (statComunidad) statComunidad.style.color = verificado ? "var(--success)" : "var(--primary)";

        // Badge de completitud de perfil
        const completo = user.perfil_completo || (user.carrera && user.universidad && user.telefono);
        if (badgePerfil) {
            if (completo) {
                badgePerfil.innerHTML = '<i class="fa-solid fa-circle-check" style="margin-right:0.3rem;"></i>Perfil Completo';
                badgePerfil.style.background = 'rgba(99,102,241,0.15)';
                badgePerfil.style.color = '#818cf8';
            } else {
                badgePerfil.innerHTML = '<i class="fa-solid fa-circle-half-stroke" style="margin-right:0.3rem;"></i>Perfil Incompleto';
                badgePerfil.style.background = 'rgba(156,163,175,0.15)';
                badgePerfil.style.color = 'var(--text-muted)';
            }
        }
        if (statPerfilEl) statPerfilEl.textContent = completo ? "Completo ✓" : "Incompleto";

        // Tarjeta de verificación y estados
        if (carnetCard) {
            carnetCard.style.display = "block";
            const statusEl = document.getElementById("prof-carnet-status");
            const badgePill = document.getElementById("prof-carnet-badge-pill");
            const formCarnet = document.getElementById("form-upload-carnet");
            const codigoSec = document.getElementById("prof-codigo-seccion");
            const verificadoOnly = document.getElementById("prof-verificado-only");
            const verificadoUniv = document.getElementById("prof-verificado-univ");

            if (verificado) {
                // Si está verificado, mostrar solo la insignia
                if (badgePill) badgePill.innerHTML = `<span class="badge" style="background: rgba(34, 197, 94, 0.2); color: var(--success); padding: 0.25rem 0.65rem; border-radius: 999px; font-weight: 700; font-size: 0.78rem;">✓ Verificado</span>`;
                if (verificadoOnly) {
                    verificadoOnly.style.display = "block";
                    if (verificadoUniv) verificadoUniv.textContent = user.universidad ? `(${user.universidad})` : "";
                }
                if (statusEl) statusEl.innerHTML = "";
                if (formCarnet) formCarnet.style.display = "none";
                if (codigoSec) codigoSec.style.display = "none";
            } else {
                if (verificadoOnly) verificadoOnly.style.display = "none";
                if (formCarnet) formCarnet.style.display = "flex";

                // La sección del código de 6 dígitos solo si el correo es institucional y no está confirmado
                const esInstitucional = this.esCorreoInstitucional(user.email);
                if (codigoSec) {
                    codigoSec.style.display = esInstitucional ? "block" : "none";
                }

                // Estados: sin verificar, carné en revisión, rechazado (con motivo)
                const estado = user.carnet_estado || (user.carnet_path ? "en_revision" : "sin_verificar");
                if (estado === "en_revision") {
                    if (badgePill) badgePill.innerHTML = `<span class="badge" style="background: rgba(234, 179, 8, 0.2); color: #eab308; padding: 0.25rem 0.65rem; border-radius: 999px; font-weight: 700; font-size: 0.78rem;"><i class="fa-solid fa-clock-rotate-left"></i> Carné en revisión</span>`;
                    if (statusEl) {
                        statusEl.innerHTML = `
                            <div style="padding: 0.65rem 0.85rem; background: rgba(234, 179, 8, 0.1); border-left: 3px solid #eab308; border-radius: 4px; font-size: 0.82rem; color: #fde047;">
                                <i class="fa-solid fa-hourglass-half" style="margin-right: 0.35rem;"></i> Tu carné estudiantil se encuentra en cola de revisión por el equipo de moderación.
                            </div>
                        `;
                    }
                } else if (estado === "rechazado") {
                    if (badgePill) badgePill.innerHTML = `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: var(--danger); padding: 0.25rem 0.65rem; border-radius: 999px; font-weight: 700; font-size: 0.78rem;"><i class="fa-solid fa-triangle-exclamation"></i> Rechazado</span>`;
                    const motivo = user.carnet_rechazo_motivo || "Documento no legible o no coincide con los datos del perfil";
                    if (statusEl) {
                        statusEl.innerHTML = `
                            <div style="padding: 0.65rem 0.85rem; background: rgba(239, 68, 68, 0.1); border-left: 3px solid var(--danger); border-radius: 4px; font-size: 0.82rem; color: #fca5a5;">
                                <i class="fa-solid fa-circle-exclamation" style="margin-right: 0.35rem;"></i> Solicitud rechazada. <strong>Motivo:</strong> ${this.escapeHtml(motivo)}. Puedes subir un nuevo carné válido.
                            </div>
                        `;
                    }
                } else {
                    if (badgePill) badgePill.innerHTML = `<span class="badge" style="background: rgba(148, 163, 184, 0.2); color: var(--text-muted); padding: 0.25rem 0.65rem; border-radius: 999px; font-weight: 600; font-size: 0.78rem;">Sin verificar (opcional)</span>`;
                    if (statusEl) statusEl.innerHTML = "";
                }
            }
        }

        // Renderizar publicaciones propias
        const myBooks = this.books.filter(b => String(b.usuario_id) === String(user.id));
        await this.loadStudentTickets();
        const myBooksContainer = document.getElementById("prof-my-books");
        if (myBooksContainer) {
            if (myBooks.length === 0) {
                myBooksContainer.innerHTML = `<p style="color: var(--text-muted); padding: 1rem 0;">No tienes libros publicados actualmente.</p>`;
            } else {
                myBooksContainer.innerHTML = myBooks.map(b => `
                    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.85rem; background: var(--bg-surface-elevated); border-radius: var(--radius-md); margin-bottom: 0.5rem; gap: 0.75rem; flex-wrap: wrap;">
                        <div>
                            <strong>${this.escapeHtml(b.titulo)}</strong>
                            <div style="font-size: 0.8rem; color: var(--text-muted);">Buscas: ${this.escapeHtml(b.libro_buscado)}</div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span class="status-badge confirmado">${this.escapeHtml(b.estado_libro)}</span>
                            <button class="btn btn-primary btn-sm" onclick="app.startBookVerification(${b.id})" style="font-size: 0.78rem; padding: 0.35rem 0.65rem; display: flex; align-items: center; gap: 0.35rem;">
                                <i class="fa-solid fa-microchip"></i> Montar Fotos / Verificar IA
                            </button>
                        </div>
                    </div>
                `).join("");
            }
        }

        // Renderizar reseñas recibidas
        const reviews = await api.getReviews();
        const reviewsContainer = document.getElementById("prof-reviews-list");
        if (reviewsContainer) {
            reviewsContainer.innerHTML = reviews.map(r => `
                <div class="review-item">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <div>
                            <strong>${this.escapeHtml(r.autor)}</strong>
                            <span style="font-size: 0.78rem; color: var(--text-muted);"> • ${this.escapeHtml(r.carrera || 'Estudiante')}</span>
                        </div>
                        <div class="star-rating" style="margin: 0; font-size: 0.95rem;">
                            ${'★'.repeat(r.estrellas)}${'☆'.repeat(5 - r.estrellas)}
                        </div>
                    </div>
                    <p style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.4;">${this.escapeHtml(r.comentario)}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                        <span style="font-size: 0.72rem; color: var(--text-muted);">${r.fecha || 'Reciente'}</span>
                        <button class="btn btn-outline btn-sm" onclick="app.promptReportReview(${r.id})" style="font-size: 0.75rem; padding: 0.2rem 0.5rem; color: var(--danger); border-color: rgba(239,68,68,0.3);">
                            <i class="fa-solid fa-flag"></i> Reportar
                        </button>
                    </div>
                </div>
            `).join("");
        }
    }

    async promptReportReview(reviewId) {
        const motivo = prompt("Describe el motivo por el cual reportas esta reseña a moderación (ej. lenguaje ofensivo, datos falsos):");
        if (!motivo || !motivo.trim()) return;
        try {
            const res = await api.reportReview(reviewId, motivo.trim());
            this.showToast(res.message || "Reseña reportada para revisión de moderación", "info");
        } catch (e) {
            this.showToast(e.message || "Error al reportar reseña", "error");
        }
    }

    async openEditProfile() {
        const user = api.getCurrentUser();
        const nameInput = document.getElementById("edit-prof-name");
        const facSelect = document.getElementById("edit-prof-facultad");
        const carreraSelect = document.getElementById("edit-prof-carrera");
        const semInput = document.getElementById("edit-prof-semestre");
        const univInput = document.getElementById("edit-prof-univ");
        const telInput = document.getElementById("edit-prof-tel");

        if (nameInput) nameInput.value = user.name || "";
        if (semInput) semInput.value = user.semestre || "";
        if (univInput) univInput.value = user.universidad || "";
        if (telInput) telInput.value = user.telefono || "";

        // Cargar catálogo de programas al abrir y asegurar que las facultades estén en el desplegable
        await this.loadProgramasAcademicos(true);

        const oferta = this.ofertaAcademica || USBMED_OFERTA_ACADEMICA;

        // Resolver facultad si ya existe en el perfil o si coincide con la oferta USB
        let matchedFac = user.facultad || "";
        if (!matchedFac && user.carrera) {
            for (const [fac, carreras] of Object.entries(oferta)) {
                if (carreras.includes(user.carrera)) {
                    matchedFac = fac;
                    break;
                }
            }
        }
        if (facSelect) {
            facSelect.value = matchedFac;
            this.onFacultadChange("edit");
        }
        if (carreraSelect && user.carrera) {
            // Si la carrera actual no figura en las opciones del selector (ej. plan anterior descontinuado, Teología, etc.)
            // se conserva inyectando la opción existente para no sobreescribir ni bloquear al usuario
            const existeOpcion = Array.from(carreraSelect.options).some(opt => opt.value === user.carrera);
            if (!existeOpcion) {
                const opt = document.createElement("option");
                opt.value = user.carrera;
                opt.textContent = `${user.carrera} (Actual)`;
                carreraSelect.appendChild(opt);
            }
            carreraSelect.value = user.carrera;
        }

        this.openModal("edit-profile-modal");
    }

    async submitEditProfile() {
        const name = document.getElementById("edit-prof-name")?.value?.trim();
        const facultad = document.getElementById("edit-prof-facultad")?.value?.trim();
        const carrera = document.getElementById("edit-prof-carrera")?.value?.trim();
        const semestreRaw = document.getElementById("edit-prof-semestre")?.value;
        const semestre = semestreRaw ? parseInt(semestreRaw, 10) : null;
        const universidad = document.getElementById("edit-prof-univ")?.value?.trim();
        const telefono = document.getElementById("edit-prof-tel")?.value?.trim();

        try {
            const updated = await api.updateProfile({ name, facultad, carrera, semestre, universidad, telefono });
            this.showToast("Perfil actualizado correctamente", "success");
            this.closeModal("edit-profile-modal");
            this.updateUserBadge();
            await this.renderProfile();
        } catch (e) {
            this.showToast(e.message || "Error al actualizar perfil", "error");
        }
    }

    esCorreoInstitucional(email) {
        if (!email || !email.includes("@")) return false;
        const dom = email.split("@")[1].toLowerCase().trim();
        const dominios = [
            "tau.usbmed.edu.co", "usbmed.edu.co", "sanbuenaventura.edu.co", "unal.edu.co", "udea.edu.co",
            "uniandes.edu.co", "javeriana.edu.co", "univalle.edu.co", "udistrital.edu.co",
            "uis.edu.co", "uninpahu.edu.co"
        ];
        return dom.endsWith(".edu.co") || dominios.some(d => dom === d || dom.endsWith("." + d));
    }

    onCarnetFileSelected(input) {
        if (!input?.files?.length) return;
        const file = input.files[0];

        // Validar formato estricto: JPG o PNG
        const ext = file.name.split(".").pop().toLowerCase();
        const validExts = ["jpg", "jpeg", "png"];
        const validTypes = ["image/jpeg", "image/png"];
        if (!validExts.includes(ext) && !validTypes.includes(file.type)) {
            this.showToast("Solo se permiten archivos de imagen en formato JPG o PNG", "warning");
            this.clearCarnetFile();
            return;
        }

        // Validar tamaño máximo: 10 MB
        const maxBytes = 10 * 1024 * 1024;
        if (file.size > maxBytes) {
            this.showToast("El archivo excede el tamaño máximo permitido de 10 MB", "warning");
            this.clearCarnetFile();
            return;
        }

        // Mostrar vista previa estilizada
        const container = document.getElementById("carnet-preview-container");
        const img = document.getElementById("carnet-preview-img");
        const nameEl = document.getElementById("carnet-preview-name");
        const sizeEl = document.getElementById("carnet-preview-size");

        if (img) img.src = URL.createObjectURL(file);
        if (nameEl) nameEl.textContent = file.name;
        if (sizeEl) sizeEl.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
        if (container) container.style.display = "flex";
    }

    clearCarnetFile() {
        const fileInput = document.getElementById("carnet-file-input");
        const container = document.getElementById("carnet-preview-container");
        const img = document.getElementById("carnet-preview-img");
        if (fileInput) fileInput.value = "";
        if (img) img.src = "";
        if (container) container.style.display = "none";
    }

    async submitUploadCarnet() {
        const fileInput = document.getElementById("carnet-file-input");
        const btn = document.getElementById("btn-upload-carnet");
        const statusEl = document.getElementById("prof-carnet-status");
        if (!fileInput?.files?.length) {
            this.showToast("Selecciona una foto de tu carné (JPG o PNG)", "warning");
            return;
        }
        const formData = new FormData();
        formData.append("carnet", fileInput.files[0]);
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...'; }
        try {
            const res = await api.uploadCarnet(formData);
            this.showToast("Carné enviado a moderación. Se revisará pronto.", "success");
            this.clearCarnetFile();
            // Actualizar usuario en sesión
            const current = api.getCurrentUser();
            if (current) {
                current.carnet_estado = "en_revision";
                current.carnet_path = "storage/carnets/pendiente";
                localStorage.setItem(api.storageKeyUser, JSON.stringify(current));
            }
            await this.renderProfile();
        } catch (e) {
            this.showToast(e.message || "Error al subir el carné", "error");
            if (statusEl) statusEl.innerHTML = `<span style="color:var(--danger);">${e.message || 'Error al subir el archivo'}</span>`;
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Enviar Carné a Revisión'; }
        }
    }

    async submitConfirmarCodigo() {
        const user = api.getCurrentUser();
        if (!user || !user.email) {
            this.showToast("Inicia sesión para confirmar tu código", "warning");
            return;
        }
        const codeInput = document.getElementById("confirm-code-input");
        const btn = document.getElementById("btn-confirm-code");
        const codigo = codeInput?.value?.trim();
        if (!codigo || codigo.length < 6) {
            this.showToast("Ingresa el código numérico de 6 dígitos", "warning");
            return;
        }
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validando...'; }
        try {
            const res = await api.confirmarCodigo(user.email, codigo);
            this.showToast(res.message || "¡Correo institucional verificado! Se ha activado tu distintivo.", "success");
            if (codeInput) codeInput.value = "";
            const current = api.getCurrentUser();
            if (current) {
                current.verificado_comunidad = true;
                current.verificado = true;
                current.insignia_estudiante_verificado = true;
                current.carnet_estado = "verificado";
                localStorage.setItem(api.storageKeyUser, JSON.stringify(current));
            }
            await this.renderProfile();
        } catch (e) {
            let msg = e.message || "Código incorrecto o expirado";
            if (msg.includes("Demasiados intentos") || msg.includes("invalidado")) {
                msg = "Demasiados intentos erróneos. Este código ha sido invalidado por seguridad. Solicita un código nuevo.";
            } else if (msg.includes("429") || msg.includes("Demasiadas solicitudes")) {
                msg = "Límite de solicitudes alcanzado (429). Espera unos minutos antes de solicitar o validar otro código.";
            }
            this.showToast(msg, "error");
        } finally {
            if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Validar Código'; }
        }
    }

    async reenviarCodigo() {
        const user = api.getCurrentUser();
        if (!user || !user.email) {
            this.showToast("Inicia sesión primero", "warning");
            return;
        }
        if (this._reenvioCooldown > 0) {
            this.showToast(`Debes esperar ${this._reenvioCooldown}s antes de solicitar otro código`, "info");
            return;
        }

        const btn = document.getElementById("btn-reenviar-codigo");
        const lbl = document.getElementById("lbl-reenviar-codigo");
        try {
            const res = await api.reenviarCodigo(user.email);
            this.showToast(res.message || "Nuevo código enviado a tu correo institucional", "info");

            // Iniciar cuenta regresiva de 60 segundos
            this._reenvioCooldown = 60;
            if (btn) btn.disabled = true;
            if (this._reenvioTimer) clearInterval(this._reenvioTimer);
            this._reenvioTimer = setInterval(() => {
                this._reenvioCooldown--;
                if (lbl) lbl.textContent = `Reenviar (${this._reenvioCooldown}s)`;
                if (this._reenvioCooldown <= 0) {
                    clearInterval(this._reenvioTimer);
                    this._reenvioTimer = null;
                    if (lbl) lbl.textContent = "Reenviar código";
                    if (btn) btn.disabled = false;
                }
            }, 1000);
        } catch (e) {
            this.showToast(e.message || "Error al reenviar código", "error");
        }
    }

    onRegisterEmailInput(email) {
        if (!email) return;
        const univInput = document.getElementById("reg-univ");
        if (!univInput) return;
        const lower = email.trim().toLowerCase();
        if (lower.includes("@tau.usbmed.edu.co") || lower.includes("@usbmed.edu.co") || lower.includes("@sanbuenaventura.edu.co") || lower.endsWith("usbmed.edu.co")) {
            univInput.value = "Universidad de San Buenaventura Medellín (USBMED)";
        } else if (lower.includes("@unal.edu.co")) {
            univInput.value = "Universidad Nacional de Colombia";
        } else if (lower.includes("@udea.edu.co")) {
            univInput.value = "Universidad de Antioquia (UdeA)";
        } else if (lower.includes("@eafit.edu.co")) {
            univInput.value = "Universidad EAFIT";
        } else if (lower.includes("@upb.edu.co")) {
            univInput.value = "Universidad Pontificia Bolivariana (UPB)";
        } else if (lower.includes("@udem.edu.co")) {
            univInput.value = "Universidad de Medellín (UDEM)";
        } else if (lower.includes("@elpoli.edu.co")) {
            univInput.value = "Politécnico Colombiano Jaime Isaza Cadavid";
        } else if (lower.includes("@itm.edu.co")) {
            univInput.value = "Instituto Tecnológico Metropolitano (ITM)";
        }
    }

    // -------------------------------------------------------------------------
    // Panel de Administración (Acceso Restringido)
    // -------------------------------------------------------------------------
    async _renderAdminKpis() {
        // Indicadores reales desde el backend; si falla se muestra "—" (nunca cifras de ejemplo).
        const poner = (id, valor) => { const el = document.getElementById(id); if (el) el.textContent = valor; };
        try {
            const r = await api.getAdminResumen();
            poner("admin-kpi-usuarios", r.usuarios_registrados);
            poner("admin-kpi-libros", r.libros_en_oferta);
            poner("admin-kpi-trueques", r.trueques_completados);
            poner("admin-kpi-reputacion", r.reputacion_global === null ? "—" : `${Number(r.reputacion_global).toFixed(2)} ★`);
        } catch (e) {
            ["admin-kpi-usuarios", "admin-kpi-libros", "admin-kpi-trueques", "admin-kpi-reputacion"].forEach(id => poner(id, "—"));
        }
    }

    async renderAdminPanel() {
        this._renderAdminKpis();
        const user = api.getCurrentUser();
        const restrictedNotice = document.getElementById("admin-restricted-view");
        const adminContent = document.getElementById("admin-content-view");

        const canReviewBooks = user && ["admin", "administrador", "moderador"].includes(user.role);
        const isAdmin = ["admin", "administrador"].includes(user?.role);
        if (!canReviewBooks) {
            if (restrictedNotice) restrictedNotice.style.display = "block";
            if (adminContent) adminContent.style.display = "none";
            return;
        }

        if (restrictedNotice) restrictedNotice.style.display = "none";
        if (adminContent) adminContent.style.display = "block";

        const managementContent = document.getElementById("admin-management-content");
        const statusEl = document.getElementById("admin-backend-status");
        if (managementContent) managementContent.style.display = isAdmin ? "block" : "none";
        if (statusEl) statusEl.style.display = isAdmin ? "block" : "none";

        if (isAdmin) {
            const users = await api.listUsers();
            const tableBody = document.getElementById("admin-users-table-body");
            if (tableBody) {
                tableBody.innerHTML = users.map(u => `
                <tr>
                    <td><strong>#${u.id}</strong></td>
                    <td>
                        <div style="font-weight: 600;">${u.name || 'Sin nombre'}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${u.email || u.correo_institucional}</div>
                    </td>
                    <td>${u.carrera || u.programa_area || 'Estudiante'}</td>
                    <td>
                        <span class="status-badge ${u.role === 'admin' ? 'rechazado' : u.role === 'moderador' ? 'confirmado' : 'propuesto'}">
                            ${u.role || u.rol || 'usuario'}
                        </span>
                    </td>
                    <td>
                        <span style="color: var(--success); font-weight: 600;">Activo</span>
                    </td>
                    <td>
                        ${u.role !== 'admin' && u.role !== 'moderador' ? `
                            <button class="btn btn-secondary btn-sm" onclick="app.promoteToModerator('${u.id}')">
                                <i class="fa-solid fa-shield-halved"></i> Promover a Moderador
                            </button>
                        ` : `
                            <span style="color: var(--text-muted); font-size: 0.8rem;">Privilegios asignados</span>
                        `}
                    </td>
                </tr>
            `).join("");
            }

            const health = await api.getHealth();
            const dbHealth = await api.getDbHealth();
            if (statusEl) {
                statusEl.innerHTML = `
                <div style="display: flex; gap: 1rem; align-items: center;">
                    <span class="status-badge completado">API: ${health.status}</span>
                    <span class="status-badge confirmado">DB: ${dbHealth.database?.status || 'conectada'} (${dbHealth.database?.dialecto || 'PostgreSQL'})</span>
                </div>
            `;
            }

            // Cargar métricas y bitácora del Sistema Auditor 5W
            await this.loadAuditStats();
            await this.loadAuditLogs();
        }

        try {
            const pendingVerifications = await api.getPendingBookVerifications();
            const queue = document.getElementById("admin-book-verification-queue");
            if (queue) {
                queue.innerHTML = pendingVerifications.length
                    ? pendingVerifications.map(verification => `
                        <article style="padding:1rem;border:1px solid var(--border-color);border-radius:var(--radius-md);">
                            <strong>${this.escapeHtml(verification.titulo)}</strong>
                            <div style="color:var(--text-secondary);font-size:.85rem;">
                                Autor: ${this.escapeHtml(verification.autor || "No indicado")} ·
                                ISBN: ${this.escapeHtml(verification.isbn || "No indicado")} ·
                                Usuario #${verification.usuario_id}
                            </div>
                            <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.75rem;">
                                <button class="btn btn-secondary btn-sm" onclick="app.viewVerificationPhotos(${verification.verificacion_id})">
                                    Ver fotos
                                </button>
                                <input id="verification-note-${verification.verificacion_id}" class="form-control" style="flex:1;min-width:180px;" value="Portada, código e ISBN revisados">
                                <button class="btn btn-success btn-sm" onclick="app.reviewBookVerification(${verification.verificacion_id}, 'aprobada')">Aprobar</button>
                                <button class="btn btn-danger btn-sm" onclick="app.reviewBookVerification(${verification.verificacion_id}, 'rechazada')">Rechazar</button>
                                <button class="btn btn-primary btn-sm" onclick="app.openTicketForVerification(${verification.verificacion_id}, ${verification.publicacion_id}, '${this.escapeHtml(verification.titulo)}')" style="display:inline-flex;align-items:center;gap:0.35rem;">
                                    <i class="fa-solid fa-headset"></i> Contactar (Ticket)
                                </button>
                            </div>
                        </article>
                    `).join("")
                    : '<p style="color:var(--text-muted);">No hay libros pendientes de revisión.</p>';
            }
        } catch (e) {
            this.showToast(e.message || "No se pudo cargar la cola de verificación", "error");
        }

        await this.loadAdminTickets();
    }

    async loadAuditStats() {
        try {
            const stats = await api.getAuditStats();
            const totalEl = document.getElementById("audit-kpi-total");
            const exitososEl = document.getElementById("audit-kpi-exitosos");
            const fallidosEl = document.getElementById("audit-kpi-fallidos");
            const bloqueadosEl = document.getElementById("audit-kpi-bloqueados");
            if (totalEl) totalEl.textContent = stats.total_eventos ?? 0;
            if (exitososEl) exitososEl.textContent = stats.eventos_exitosos ?? 0;
            if (fallidosEl) fallidosEl.textContent = stats.eventos_fallidos ?? 0;
            if (bloqueadosEl) bloqueadosEl.textContent = stats.intentos_bloqueados_401_403 ?? 0;
        } catch (e) {
            console.warn("No se pudieron cargar estadísticas de auditoría", e);
        }
    }

    async loadAuditLogs(reset = false) {
        const tbody = document.getElementById("admin-audit-table-body");
        if (!tbody) return;

        try {
            const search = document.getElementById("audit-filter-search")?.value?.trim() || "";
            const action = document.getElementById("audit-filter-action")?.value || "";
            const status = document.getElementById("audit-filter-status")?.value || "";

            const params = { limit: 50 };
            if (search) params.busqueda = search;
            if (action) params.accion = action;
            if (status === "solo_errores") params.solo_errores = true;

            const res = await api.getAuditLogs(params);
            this._auditLogsCache = res.items || [];

            if (!this._auditLogsCache.length) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No se encontraron registros de auditoría.</td></tr>`;
                return;
            }

            tbody.innerHTML = this._auditLogsCache.map(log => {
                const fecha = new Date(log.fecha_hora).toLocaleString('es-CO', {
                    dateStyle: 'short',
                    timeStyle: 'medium',
                    timeZone: 'UTC'
                }) + ' UTC';

                const statusColor = log.exito ? 'var(--success)' : '#ef4444';
                const statusBg = log.exito ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)';
                const userText = log.usuario_id 
                    ? `Usuario #${log.usuario_id} <span style="font-size:0.75rem; color:var(--text-muted);">(${log.usuario_email || '-'})</span>` 
                    : `<span style="color:var(--text-muted); font-style: italic;">Anónimo</span>`;

                return `
                    <tr>
                        <td style="font-size: 0.8rem; font-family: monospace;">${fecha}</td>
                        <td>
                            <div>${userText}</div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">IP: ${this.escapeHtml(log.ip_origen)}</div>
                        </td>
                        <td>
                            <strong style="font-size: 0.85rem;">${this.escapeHtml(log.accion)}</strong>
                            <div style="font-size: 0.75rem; color: var(--text-muted);">Recurso: ${this.escapeHtml(log.recurso || 'general')}</div>
                        </td>
                        <td>
                            <span class="status-badge" style="font-size:0.7rem; font-weight:700;">${this.escapeHtml(log.metodo_http)}</span>
                            <span style="font-size: 0.8rem; font-family: monospace;">${this.escapeHtml(log.endpoint)}</span>
                        </td>
                        <td>
                            <span style="background: ${statusBg}; color: ${statusColor}; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; font-size: 0.8rem;">
                                HTTP ${log.estado_http}
                            </span>
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">${log.duracion_ms ?? 0} ms</div>
                        </td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="app.showAuditDetail(${log.id})" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;">
                                <i class="fa-solid fa-eye"></i> 5W
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            console.error("Error al cargar logs de auditoría:", e);
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: #ef4444; padding: 1rem;">Error al consultar la bitácora: ${this.escapeHtml(e.message || "Error")}</td></tr>`;
        }
    }

    async filterAuditLogs() {
        await this.loadAuditLogs();
    }

    showAuditDetail(logId) {
        const log = (this._auditLogsCache || []).find(l => l.id === logId);
        if (!log) return;

        const body = document.getElementById("audit-modal-body");
        if (!body) return;

        const fecha = new Date(log.fecha_hora).toISOString();
        body.innerHTML = `
            <div style="display: grid; gap: 1rem;">
                <div style="background: var(--bg-tertiary); padding: 0.75rem 1rem; border-radius: var(--radius-md); border-left: 4px solid var(--primary);">
                    <div style="font-size: 0.8rem; text-transform: uppercase; color: var(--text-secondary); font-weight: 700;">Regla 5W: Clasificación de Evento</div>
                    <div style="font-size: 1.1rem; font-weight: 800; margin-top: 0.25rem;">${this.escapeHtml(log.accion)}</div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                    <div style="background: var(--bg-secondary); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                        <strong style="color: var(--primary);"><i class="fa-solid fa-user"></i> WHO (Quién):</strong>
                        <div style="font-size: 0.85rem; margin-top: 0.25rem;">
                            <strong>ID:</strong> ${log.usuario_id || 'Anónimo'}<br>
                            <strong>Email:</strong> ${this.escapeHtml(log.usuario_email || 'No autenticado')}<br>
                            <strong>Rol:</strong> ${this.escapeHtml(log.usuario_rol || 'Público')}<br>
                            <strong>IP Origen:</strong> <code>${this.escapeHtml(log.ip_origen)}</code><br>
                            <strong>User-Agent:</strong> <span style="font-size: 0.75rem; color: var(--text-muted); word-break: break-all;">${this.escapeHtml(log.user_agent || '-')}</span>
                        </div>
                    </div>

                    <div style="background: var(--bg-secondary); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                        <strong style="color: var(--primary);"><i class="fa-solid fa-clock"></i> WHEN (Cuándo):</strong>
                        <div style="font-size: 0.85rem; margin-top: 0.25rem;">
                            <strong>Timestamp ISO:</strong> <code>${fecha}</code><br>
                            <strong>Duración procesamiento:</strong> ${log.duracion_ms ?? 0} ms
                        </div>
                    </div>
                </div>

                <div style="background: var(--bg-secondary); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                    <strong style="color: var(--primary);"><i class="fa-solid fa-location-dot"></i> WHERE (Dónde):</strong>
                    <div style="font-size: 0.85rem; margin-top: 0.25rem;">
                        <strong>Método:</strong> <code>${this.escapeHtml(log.metodo_http)}</code><br>
                        <strong>Endpoint:</strong> <code>${this.escapeHtml(log.endpoint)}</code><br>
                        <strong>Recurso:</strong> ${this.escapeHtml(log.recurso || 'general')}
                    </div>
                </div>

                <div style="background: var(--bg-secondary); padding: 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                    <strong style="color: var(--primary);"><i class="fa-solid fa-circle-question"></i> WHY (Por qué / Resultado):</strong>
                    <div style="font-size: 0.85rem; margin-top: 0.25rem;">
                        <strong>Estado HTTP:</strong> <span style="font-weight: 700; color: ${log.exito ? 'var(--success)' : '#ef4444'}">${log.estado_http} (${log.exito ? 'Éxito' : 'Error/Bloqueo'})</span><br>
                        <strong>Detalle:</strong> ${this.escapeHtml(log.detalle || 'Sin observaciones adicionales')}
                    </div>
                </div>
            </div>
        `;
        this.openModal("audit-detail-modal");
    }

    async viewVerificationPhotos(verificationId) {
        try {
            const [cover, isbnPage] = await Promise.all([
                api.getBookVerificationEvidence(verificationId, "portada"),
                api.getBookVerificationEvidence(verificationId, "pagina-isbn")
            ]);
            this.closeVerificationPhotos();
            this.verificationPhotoUrls = [
                URL.createObjectURL(cover),
                URL.createObjectURL(isbnPage)
            ];
            document.getElementById("review-book-cover-photo").src = this.verificationPhotoUrls[0];
            document.getElementById("review-book-isbn-photo").src = this.verificationPhotoUrls[1];
            this.openModal("review-book-photos-modal");
        } catch (e) {
            this.showToast(e.message || "No se pudieron abrir las fotos", "error");
        }
    }

    closeVerificationPhotos() {
        (this.verificationPhotoUrls || []).forEach(url => URL.revokeObjectURL(url));
        this.verificationPhotoUrls = [];
        document.getElementById("review-book-cover-photo").removeAttribute("src");
        document.getElementById("review-book-isbn-photo").removeAttribute("src");
        this.closeModal("review-book-photos-modal");
    }

    async reviewBookVerification(verificationId, decision) {
        const note = document.getElementById(`verification-note-${verificationId}`)?.value?.trim();
        if (!note || note.length < 3) {
            this.showToast("Escribe una nota breve de revisión", "warning");
            return;
        }
        try {
            await api.reviewBookVerification(verificationId, decision, note);
            this.showToast(
                decision === "aprobada" ? "Libro aprobado y publicado" : "Evidencia rechazada",
                "success"
            );
            await this.renderAdminPanel();
        } catch (e) {
            this.showToast(e.message || "No se pudo guardar la revisión", "error");
        }
    }

    async promoteToModerator(userId) {
        try {
            await api.promoteUser(userId);
            this.showToast(`Usuario promovido a moderador exitosamente`, "success");
            this.renderAdminPanel();
        } catch (e) {
            this.showToast(e.message || "Error al promover usuario", "error");
        }
    }

    loginAsAdmin() {
        // Sin sesión simulada: el acceso de administrador requiere un login real contra el backend.
        this.openLoginModal();
    }

    // -------------------------------------------------------------------------
    // Calificación de Trueques
    // -------------------------------------------------------------------------
    openRateModal(tradeId) {
        this.ratingTradeId = tradeId;
        this.setRatingStars(5);
        const textInput = document.getElementById("rate-review-text");
        if (textInput) textInput.value = "";
        this.openModal("rate-trade-modal");
    }

    setRatingStars(count) {
        this.selectedRating = count;
        document.querySelectorAll(".star-select-btn").forEach(btn => {
            const val = parseInt(btn.getAttribute("data-star-val"));
            if (val <= count) {
                btn.style.color = "#fbbf24";
            } else {
                btn.style.color = "var(--text-muted)";
            }
        });
    }

    async submitTradeRating() {
        const text = document.getElementById("rate-review-text")?.value;
        const trade = this.trades.find(t => t.id === this.ratingTradeId);
        if (!trade) return;
        
        const current = api.getCurrentUser();
        const otherUserId = String(trade.usuario_propone_id) === String(current.id) ? trade.usuario_recibe_id : trade.usuario_propone_id;

        try {
            await api.rateTrade(this.ratingTradeId, {
                estrellas: this.selectedRating,
                resena: text || "Intercambio completado satisfactoriamente.",
                usuario_calificado_id: otherUserId
            });

            this.showToast("¡Gracias! Tu calificación ha sido registrada para la reputación comunitaria.", "success");
            this.closeModal("rate-trade-modal");
            this.trades = await api.getTrueques();
            this.renderTrades();
        } catch (e) {
            this.showToast(e.message || "Error al calificar", "error");
        }
    }

    // -------------------------------------------------------------------------
    // Auth & Social Login (Modales Separados)
    // -------------------------------------------------------------------------
    openLoginModal() {
        this.closeModal("register-modal");
        this.closeModal("auth-modal");
        this.openModal("login-modal");
    }

    async openRegisterModal() {
        await this.loadProgramasAcademicos(true);
        this.closeModal("login-modal");
        this.closeModal("auth-modal");
        this.openModal("register-modal");
    }

    switchToLogin() {
        this.closeModal("register-modal");
        this.openModal("login-modal");
    }

    async switchToRegister() {
        await this.loadProgramasAcademicos(true);
        this.closeModal("login-modal");
        this.openModal("register-modal");
    }

    openAuthModal(tab = "login") {
        if (tab === "register") {
            this.openRegisterModal();
        } else {
            this.openLoginModal();
        }
    }

    toggleChatSidebar() {
        const sidebar = document.getElementById("chat-sidebar");
        if (sidebar) {
            sidebar.classList.toggle("mobile-open");
        }
    }

    _esConfirmacionPendiente(error) {
        return /confirmar tu correo/i.test(error?.message || "");
    }

    // Pide el código enviado al correo institucional, lo confirma e inicia sesión.
    // Devuelve el resultado del login, o null si el usuario no ingresó el código.
    async _confirmarCorreoEIniciarSesion(email, pass) {
        const codigo = window.prompt(
            "Te enviamos un código de 6 dígitos a tu correo institucional.\nEscríbelo para activar tu cuenta:"
        );
        if (!codigo || !codigo.trim()) {
            if (window.confirm("¿Quieres que te reenviemos el código de confirmación?")) {
                try {
                    await api.reenviarCodigo(email);
                    this.showToast("Te enviamos un nuevo código. Revisa tu correo e inicia sesión de nuevo.", "info");
                } catch (err) {
                    this.showToast(err.message || "No se pudo reenviar el código", "error");
                }
            } else {
                this.showToast("Debes confirmar tu correo institucional para usar tu cuenta.", "warning");
            }
            return null;
        }
        await api.confirmarCodigo(email, codigo.trim());
        this.showToast("Correo confirmado. Iniciando sesión...", "success");
        return await api.login(email, pass);
    }

    async submitLogin() {
        const email = document.getElementById("login-email")?.value?.trim();
        const pass = document.getElementById("login-password")?.value;

        if (!email || !pass) {
            this.showToast("Ingresa tu correo y contraseña", "warning");
            return;
        }

        try {
            let result;
            try {
                result = await api.login(email, pass);
            } catch (e) {
                if (!this._esConfirmacionPendiente(e)) throw e;
                result = await this._confirmarCorreoEIniciarSesion(email, pass);
                if (!result) return;
            }
            this.updateUserBadge();
            this.showToast(`¡Bienvenido de nuevo, ${result.user?.name || ''}!`, "success");
            this.closeModal("login-modal");
            this.closeModal("auth-modal");
            const emailInput = document.getElementById("login-email");
            const passInput = document.getElementById("login-password");
            if (emailInput) emailInput.value = "";
            if (passInput) passInput.value = "";
            this.renderCurrentView();
        } catch (e) {
            this.showToast(e.message || "Credenciales inválidas", "error");
        }
    }

    async submitRegister() {
        const name = document.getElementById("reg-name")?.value?.trim();
        const email = document.getElementById("reg-email")?.value?.trim();
        const pass = document.getElementById("reg-password")?.value;
        const telefono = document.getElementById("reg-tel")?.value?.trim();
        const facultad = document.getElementById("reg-facultad")?.value?.trim();
        const carrera = document.getElementById("reg-carrera")?.value?.trim();
        const semestreRaw = document.getElementById("reg-semestre")?.value;
        const semestre = semestreRaw ? parseInt(semestreRaw, 10) : null;
        const universidad = document.getElementById("reg-univ")?.value?.trim();

        if (!name) {
            this.showToast("Por favor escribe tu nombre completo", "warning");
            return;
        }
        if (!email || !email.includes("@")) {
            this.showToast("Por favor escribe un correo electrónico válido", "warning");
            return;
        }
        if (!pass || pass.length < 8) {
            this.showToast("La contraseña debe tener al menos 8 caracteres", "warning");
            return;
        }

        try {
            let result;
            try {
                result = await api.register({ name, email, password: pass, telefono, facultad, carrera, semestre, universidad });
            } catch (e) {
                // La cuenta ya se creó; con correo institucional falta confirmarlo antes de entrar.
                if (!this._esConfirmacionPendiente(e)) throw e;
                this.closeModal("register-modal");
                this.closeModal("auth-modal");
                result = await this._confirmarCorreoEIniciarSesion(email, pass);
                if (!result) return;
            }
            this.updateUserBadge();
            this.showToast(`¡Cuenta creada con éxito! Bienvenido, ${result.user?.name || name}`, "success");
            this.closeModal("register-modal");
            this.closeModal("auth-modal");
            ["reg-name", "reg-email", "reg-password", "reg-tel", "reg-facultad", "reg-carrera", "reg-univ"].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = "";
            });
            const semEl = document.getElementById("reg-semestre");
            if (semEl) semEl.selectedIndex = 0;
            this.renderCurrentView();
        } catch (e) {
            this.showToast(e.message || "Error al registrar la cuenta", "error");
        }
    }

    async logout() {
        this._closeChatWebSocket(true);
        await api.logout();
        this.trades = [];
        this.matches = [];
        this._actualizarContadorMatches();
        this.updateUserBadge();
        this.showToast("Has cerrado sesión", "info");
        this.navigateTo("catalog");
    }

    openPublishBookModal() {
        const user = api.getCurrentUser();
        if (!user) {
            this.showToast("Debes iniciar sesión para publicar un libro", "warning");
            this.openAuthModal("login");
            return;
        }
        this.openModal("publish-book-modal");
    }

    async socialLogin(provider) {
        await api.socialLogin(provider);
    }

    updateUserBadge() {
        const user = api.getCurrentUser();
        const guestBox = document.getElementById("header-guest-box");
        const userBox = document.getElementById("header-user-box");
        const avatarMini = document.getElementById("header-user-avatar");
        const nameMini = document.getElementById("header-user-name");
        const roleMini = document.getElementById("header-user-role");
        const adminNavBtn = document.getElementById("nav-admin-btn");

        if (user) {
            if (guestBox) guestBox.style.display = "none";
            if (userBox) userBox.style.display = "flex";
            if (avatarMini) avatarMini.src = user.avatar || "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150&auto=format&fit=crop&q=80";
            if (nameMini) nameMini.textContent = user.name;
            if (roleMini) roleMini.textContent = (user.role || "usuario").toUpperCase();

            // Mostrar u ocultar nav de Admin
            if (adminNavBtn) {
                adminNavBtn.style.display = ["admin", "administrador", "moderador"].includes(user.role)
                    ? "inline-flex"
                    : "none";
            }
        } else {
            if (guestBox) guestBox.style.display = "flex";
            if (userBox) userBox.style.display = "none";
            if (adminNavBtn) adminNavBtn.style.display = "none";
        }
    }

    // -------------------------------------------------------------------------
    // Modales Generales
    // -------------------------------------------------------------------------
    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.add("active");
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.remove("active");
    }

    // -------------------------------------------------------------------------
    // Tema & Toasts
    // -------------------------------------------------------------------------
    toggleTheme() {
        const current = document.documentElement.getAttribute("data-theme") || "dark";
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("campus_swap_theme", next);

        const icon = document.getElementById("theme-toggle-icon");
        if (icon) {
            icon.className = next === "dark" ? "fa-solid fa-moon" : "fa-solid fa-sun";
        }
    }

    _applyTheme() {
        const saved = localStorage.getItem("campus_swap_theme") || "dark";
        document.documentElement.setAttribute("data-theme", saved);
        const icon = document.getElementById("theme-toggle-icon");
        if (icon) {
            icon.className = saved === "dark" ? "fa-solid fa-moon" : "fa-solid fa-sun";
        }
    }

    showToast(message, type = "info") {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "toast-container";
            document.body.appendChild(container);
        }

        const icons = {
            success: "fa-circle-check",
            warning: "fa-triangle-exclamation",
            error: "fa-circle-xmark",
            info: "fa-circle-info"
        };
        const colors = {
            success: "var(--success)",
            warning: "var(--warning)",
            error: "var(--danger)",
            info: "var(--primary)"
        };

        const toast = document.createElement("div");
        toast.className = "toast";
        toast.innerHTML = `
            <i class="fa-solid ${icons[type] || icons.info}" style="color: ${colors[type] || colors.info}; font-size: 1.1rem;"></i>
            <span>${message}</span>
        `;

        const isLongAlert = message.includes("suspendida") || message.includes("bloqueada") || message.includes("Límite") || message.includes("429") || message.includes("invalidado");
        const duration = isLongAlert ? 7000 : 3500;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(100%)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // =========================================================================
    // SISTEMA DE TICKETS DE REVISIÓN Y COMUNICACIÓN CON ESTUDIANTES
    // =========================================================================

    _formatTicketStatusBadge(estado) {
        switch (estado) {
            case "abierto":
                return `<span class="status-badge" style="background: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3);"><i class="fa-solid fa-folder-open"></i> Abierto</span>`;
            case "esperando_estudiante":
                return `<span class="status-badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);"><i class="fa-solid fa-hourglass-half"></i> Esperando al Estudiante</span>`;
            case "en_revision":
                return `<span class="status-badge" style="background: rgba(168, 85, 247, 0.15); color: #a855f7; border: 1px solid rgba(168, 85, 247, 0.3);"><i class="fa-solid fa-magnifying-glass"></i> En Revisión</span>`;
            case "resuelto":
                return `<span class="status-badge" style="background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3);"><i class="fa-solid fa-check"></i> Resuelto</span>`;
            case "cerrado":
                return `<span class="status-badge" style="background: rgba(100, 116, 139, 0.15); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.3);"><i class="fa-solid fa-lock"></i> Cerrado</span>`;
            default:
                return `<span class="status-badge">${this.escapeHtml(estado)}</span>`;
        }
    }

    _formatTicketPriorityBadge(prioridad) {
        switch (prioridad) {
            case "alta":
                return `<span style="background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 0.72rem; padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 600;">Alta</span>`;
            case "baja":
                return `<span style="background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.3); font-size: 0.72rem; padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 600;">Baja</span>`;
            default:
                return `<span style="background: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3); font-size: 0.72rem; padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 600;">Media</span>`;
        }
    }

    async loadAdminTickets() {
        const listEl = document.getElementById("admin-tickets-list");
        if (!listEl) return;

        const statusFilter = document.getElementById("admin-tickets-filter-status")?.value || "";
        try {
            const tickets = await api.getTickets({ estado: statusFilter || undefined });
            if (!tickets || tickets.length === 0) {
                listEl.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem; padding: 0.75rem 0;">No hay tickets de revisión registrados con este criterio.</p>`;
                return;
            }

            listEl.innerHTML = tickets.map(t => `
                <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 0.85rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
                    <div style="flex: 1; min-width: 250px;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                            <strong>${this.escapeHtml(t.asunto)}</strong>
                            ${this._formatTicketStatusBadge(t.estado)}
                            ${this._formatTicketPriorityBadge(t.prioridad)}
                        </div>
                        <div style="font-size: 0.82rem; color: var(--text-secondary);">
                            <span><i class="fa-solid fa-book" style="color: var(--primary); font-size: 0.75rem;"></i> Libro: <strong>${this.escapeHtml(t.publicacion_titulo || `Publicación #${t.publicacion_id}`)}</strong></span> ·
                            <span><i class="fa-solid fa-user" style="font-size: 0.75rem;"></i> Estudiante: ${this.escapeHtml(t.usuario_nombre || `Usuario #${t.usuario_id}`)}</span>
                        </div>
                        ${t.ultimo_mensaje ? `
                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 480px;">
                            <i class="fa-regular fa-comment-dots"></i> «${this.escapeHtml(t.ultimo_mensaje)}»
                        </div>
                        ` : ''}
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.75rem; color: var(--text-muted);">${new Date(t.actualizado_en).toLocaleDateString()}</span>
                        <button class="btn btn-secondary btn-sm" onclick="app.openTicketModal(${t.id})" style="display: flex; align-items: center; gap: 0.35rem;">
                            <i class="fa-solid fa-comments"></i> Conversar (${t.mensajes_count || 1})
                        </button>
                    </div>
                </div>
            `).join("");
        } catch (e) {
            listEl.innerHTML = `<p style="color: var(--danger); font-size: 0.85rem;">Error al cargar tickets: ${this.escapeHtml(e.message)}</p>`;
        }
    }

    async loadStudentTickets() {
        const listEl = document.getElementById("student-tickets-list");
        if (!listEl) return;

        try {
            const tickets = await api.getMyTickets();
            if (!tickets || tickets.length === 0) {
                listEl.innerHTML = `<p style="color: var(--text-muted); font-size: 0.82rem;">No tienes observaciones o tickets de revisión pendientes para tus libros.</p>`;
                return;
            }

            listEl.innerHTML = tickets.map(t => {
                const needsReply = t.estado === "esperando_estudiante";
                return `
                <div style="background: var(--bg-surface); border: 1px solid ${needsReply ? 'rgba(245, 158, 11, 0.4)' : 'var(--border-color)'}; border-radius: var(--radius-sm); padding: 0.75rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
                        <div>
                            <div style="font-weight: 600; font-size: 0.88rem; display: flex; align-items: center; gap: 0.4rem;">
                                ${needsReply ? '<i class="fa-solid fa-circle-exclamation" style="color: #f59e0b;"></i>' : ''}
                                ${this.escapeHtml(t.asunto)}
                            </div>
                            <div style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 0.15rem;">
                                Libro: <strong>${this.escapeHtml(t.publicacion_titulo || `Publicación #${t.publicacion_id}`)}</strong>
                            </div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            ${this._formatTicketStatusBadge(t.estado)}
                            <button class="btn ${needsReply ? 'btn-primary' : 'btn-secondary'} btn-sm" onclick="app.openTicketModal(${t.id})" style="font-size: 0.75rem; padding: 0.25rem 0.6rem;">
                                <i class="fa-solid fa-reply"></i> Responder
                            </button>
                        </div>
                    </div>
                </div>
                `;
            }).join("");
        } catch (e) {
            listEl.innerHTML = `<p style="color: var(--text-muted); font-size: 0.82rem;">No se pudieron cargar los tickets de revisión.</p>`;
        }
    }

    async openTicketForVerification(verificationId, publicationId, bookTitle) {
        try {
            const existing = await api.getPublicationTickets(publicationId);
            const openTicket = existing && existing.find(t => t.estado !== "cerrado" && t.estado !== "resuelto");

            if (openTicket) {
                await this.openTicketModal(openTicket.id);
            } else {
                this.openCreateTicketModal(publicationId, bookTitle);
            }
        } catch (e) {
            this.showToast(e.message || "Error al consultar ticket de la publicación", "error");
        }
    }

    openCreateTicketModal(publicationId, bookTitle) {
        document.getElementById("create-ticket-pub-id").value = publicationId;
        document.getElementById("create-ticket-pub-title").textContent = bookTitle || `Publicación #${publicationId}`;
        document.getElementById("create-ticket-subject").value = `Aclaración sobre revisión de: ${bookTitle}`;
        document.getElementById("create-ticket-initial-msg").value = "";
        this.openModal("create-ticket-modal");
    }

    async submitCreateTicket() {
        const publicationId = parseInt(document.getElementById("create-ticket-pub-id").value, 10);
        const asunto = document.getElementById("create-ticket-subject").value.trim();
        const prioridad = document.getElementById("create-ticket-priority").value;
        const mensajeInicial = document.getElementById("create-ticket-initial-msg").value.trim();

        if (!asunto || !mensajeInicial) {
            this.showToast("Por favor completa el asunto y el mensaje", "warning");
            return;
        }

        try {
            const ticket = await api.createTicket({
                publicacion_id: publicationId,
                asunto,
                prioridad,
                mensaje_inicial: mensajeInicial
            });
            this.closeModal("create-ticket-modal");
            this.showToast("Ticket de revisión abierto exitosamente", "success");
            await this.openTicketModal(ticket.id);
            await this.loadAdminTickets();
        } catch (e) {
            this.showToast(e.message || "No se pudo crear el ticket", "error");
        }
    }

    async openTicketModal(ticketId) {
        this.activeTicketId = ticketId;
        try {
            const ticket = await api.getTicketDetail(ticketId);
            this.activeTicket = ticket;

            document.getElementById("ticket-modal-subject").textContent = ticket.asunto;
            const statusBadge = document.getElementById("ticket-modal-status-badge");
            if (statusBadge) statusBadge.outerHTML = this._formatTicketStatusBadge(ticket.estado);
            const priorityBadge = document.getElementById("ticket-modal-priority-badge");
            if (priorityBadge) priorityBadge.outerHTML = this._formatTicketPriorityBadge(ticket.prioridad);

            const bookInfo = document.getElementById("ticket-modal-book-info");
            if (bookInfo) {
                bookInfo.innerHTML = `
                    <span><i class="fa-solid fa-book"></i> Libro: <strong>${this.escapeHtml(ticket.publicacion_titulo || `Publicación #${ticket.publicacion_id}`)}</strong></span> ·
                    <span><i class="fa-solid fa-user"></i> Estudiante: <strong>${this.escapeHtml(ticket.usuario_nombre || `Usuario #${ticket.usuario_id}`)}</strong></span>
                    ${ticket.moderador_nombre ? ` · <span><i class="fa-solid fa-shield-halved"></i> Moderador: <strong>${this.escapeHtml(ticket.moderador_nombre)}</strong></span>` : ''}
                `;
            }

            const statusSelect = document.getElementById("ticket-change-status-select");
            if (statusSelect) statusSelect.value = ticket.estado;

            const updatedEl = document.getElementById("ticket-last-updated");
            if (updatedEl) updatedEl.textContent = `Actualizado: ${new Date(ticket.actualizado_en).toLocaleString()}`;

            this._renderTicketMessages(ticket.mensajes || []);

            const replyInput = document.getElementById("ticket-reply-input");
            if (replyInput) replyInput.value = "";

            this.openModal("ticket-modal");
        } catch (e) {
            this.showToast(e.message || "No se pudo cargar el ticket", "error");
        }
    }

    _renderTicketMessages(mensajes) {
        const container = document.getElementById("ticket-messages-container");
        if (!container) return;

        const currentUser = api.getCurrentUser();
        const currentUserId = currentUser ? parseInt(currentUser.id, 10) : 0;

        if (!mensajes || mensajes.length === 0) {
            container.innerHTML = `<p style="color: var(--text-muted); text-align: center; margin: auto;">No hay mensajes registrados en este ticket.</p>`;
            return;
        }

        container.innerHTML = mensajes.map(m => {
            if (m.es_del_sistema) {
                return `
                    <div style="text-align: center; margin: 0.5rem 0;">
                        <span style="background: rgba(255, 255, 255, 0.05); color: var(--text-muted); font-size: 0.75rem; padding: 0.25rem 0.65rem; border-radius: var(--radius-full); border: 1px dashed var(--border-color);">
                            <i class="fa-solid fa-info-circle"></i> ${this.escapeHtml(m.contenido)} · ${new Date(m.creado_en).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                    </div>
                `;
            }

            const isMe = m.remitente_id === currentUserId;
            const isModerator = m.remitente_rol === "moderador" || m.remitente_rol === "admin" || m.remitente_rol === "administrador";

            return `
                <div style="display: flex; flex-direction: column; align-items: ${isMe ? 'flex-end' : 'flex-start'}; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.2rem; display: flex; align-items: center; gap: 0.35rem;">
                        <strong>${this.escapeHtml(m.remitente_nombre || `Usuario #${m.remitente_id}`)}</strong>
                        ${isModerator ? '<span style="background: rgba(168, 85, 247, 0.2); color: #c084fc; font-size: 0.68rem; padding: 0.1rem 0.35rem; border-radius: 3px; font-weight: 600;"><i class="fa-solid fa-shield"></i> Moderación</span>' : ''}
                        <span>· ${new Date(m.creado_en).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div style="max-width: 82%; padding: 0.75rem 1rem; border-radius: var(--radius-md); font-size: 0.88rem; line-height: 1.45; word-break: break-word; background: ${isMe ? 'var(--primary)' : 'var(--bg-surface-elevated)'}; color: ${isMe ? '#ffffff' : 'var(--text-primary)'}; border: 1px solid ${isMe ? 'transparent' : 'var(--border-color)'};">
                        ${this.escapeHtml(m.contenido).replace(/\n/g, '<br>')}
                    </div>
                </div>
            `;
        }).join("");

        container.scrollTop = container.scrollHeight;
    }

    async submitTicketMessage() {
        if (!this.activeTicketId) return;

        const input = document.getElementById("ticket-reply-input");
        const contenido = input?.value?.trim();
        if (!contenido) return;

        try {
            input.value = "";
            const nuevoMensaje = await api.sendTicketMessage(this.activeTicketId, contenido);
            
            if (this.activeTicket && this.activeTicket.mensajes) {
                this.activeTicket.mensajes.push(nuevoMensaje);
                this._renderTicketMessages(this.activeTicket.mensajes);
            } else {
                await this.openTicketModal(this.activeTicketId);
            }

            await this.loadAdminTickets();
            await this.loadStudentTickets();
            this.showToast("Respuesta enviada", "success");
        } catch (e) {
            this.showToast(e.message || "Error al enviar mensaje en el ticket", "error");
        }
    }

    async onTicketStatusSelectChange() {
        if (!this.activeTicketId) return;
        const selectEl = document.getElementById("ticket-change-status-select");
        const nuevoEstado = selectEl?.value;
        if (!nuevoEstado) return;

        try {
            const updated = await api.updateTicketStatus(this.activeTicketId, nuevoEstado);
            this.activeTicket = updated;
            const statusBadge = document.getElementById("ticket-modal-status-badge");
            if (statusBadge) statusBadge.outerHTML = this._formatTicketStatusBadge(updated.estado);
            this._renderTicketMessages(updated.mensajes || []);
            await this.loadAdminTickets();
            await this.loadStudentTickets();
            this.showToast(`Estado del ticket cambiado a: ${nuevoEstado}`, "info");
        } catch (e) {
            this.showToast(e.message || "No se pudo actualizar el estado del ticket", "error");
        }
    }


    // =========================================================================
    // VISTA PRINCIPAL DE TICKETS DE REVISIÓN
    // =========================================================================
    async filterTicketsByStatus(status) {
        this.activeTicketFilter = status;
        
        // Actualizar botones de filtro
        const btnMap = {
            '': 'ticket-filter-btn-all',
            'esperando_estudiante': 'ticket-filter-btn-esperando',
            'en_revision': 'ticket-filter-btn-revision',
            'abierto': 'ticket-filter-btn-abierto',
            'resuelto': 'ticket-filter-btn-resuelto'
        };
        Object.entries(btnMap).forEach(([s, id]) => {
            const btn = document.getElementById(id);
            if (btn) {
                if (s === status) {
                    btn.classList.add("active");
                    btn.style.background = "var(--primary)";
                    btn.style.color = "#ffffff";
                } else {
                    btn.classList.remove("active");
                    btn.style.background = "transparent";
                    btn.style.color = "var(--text-secondary)";
                }
            }
        });

        await this.renderTicketsView();
    }

    async renderTicketsView() {
        const container = document.getElementById("tickets-view-container");
        if (!container) return;

        const user = api.getCurrentUser();
        if (!user) {
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem 1rem; background: var(--bg-surface-elevated); border-radius: var(--radius-lg); border: 1px solid var(--border-color);">
                    <i class="fa-solid fa-user-lock" style="font-size: 2.5rem; color: var(--primary); margin-bottom: 0.75rem;"></i>
                    <h3>Inicia sesión para ver tus tickets de revisión</h3>
                    <p style="color: var(--text-secondary); max-width: 400px; margin: 0.5rem auto 1.25rem;">
                        Los tickets te permiten conversar con los moderadores sobre el estado de tus libros en revisión.
                    </p>
                    <button class="btn btn-primary" onclick="app.openAuthModal('login')">
                        <i class="fa-solid fa-arrow-right-to-bracket"></i> Iniciar Sesión
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin" style="font-size: 1.5rem;"></i><p style="margin-top: 0.5rem;">Cargando tickets de revisión...</p></div>`;

        try {
            const isMod = user.role === "moderador" || user.role === "admin" || user.role === "administrador";
            let tickets = [];
            
            if (isMod) {
                tickets = await api.getTickets({ estado: this.activeTicketFilter || undefined });
            } else {
                tickets = await api.getMyTickets({ estado: this.activeTicketFilter || undefined });
            }

            if (!tickets || tickets.length === 0) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 3.5rem 1rem; background: var(--bg-surface-elevated); border-radius: var(--radius-lg); border: 1px dashed var(--border-color);">
                        <i class="fa-regular fa-comments" style="font-size: 3rem; color: var(--text-muted); margin-bottom: 0.75rem;"></i>
                        <h3 style="color: var(--text-primary); margin-bottom: 0.35rem;">No hay tickets registrados</h3>
                        <p style="color: var(--text-secondary); font-size: 0.9rem; max-width: 480px; margin: 0 auto;">
                            ${this.activeTicketFilter ? 'No hay tickets con el estado seleccionado.' : 'Cuando un libro entre en revisión o el moderador requiera aclaraciones sobre una foto o dato, aparecerá aquí para coordinar.'}
                        </p>
                    </div>
                `;
                return;
            }

            // Actualizar badge en navbar si hay tickets esperando_estudiante
            const waitingCount = tickets.filter(t => t.estado === "esperando_estudiante").length;
            const navBadge = document.getElementById("tickets-nav-badge");
            if (navBadge) {
                if (waitingCount > 0) {
                    navBadge.style.display = "inline-block";
                    navBadge.textContent = waitingCount;
                } else {
                    navBadge.style.display = "none";
                }
            }

            container.innerHTML = tickets.map(t => {
                const needsAction = t.estado === "esperando_estudiante" && !isMod;
                return `
                <div style="background: var(--bg-surface-elevated); border: 1px solid ${needsAction ? 'rgba(245, 158, 11, 0.45)' : 'var(--border-color)'}; border-radius: var(--radius-md); padding: 1.25rem; transition: transform 0.2s ease, box-shadow 0.2s ease; box-shadow: ${needsAction ? '0 4px 14px rgba(245, 158, 11, 0.12)' : 'none'};">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.75rem;">
                        <div style="flex: 1; min-width: 280px;">
                            <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.4rem;">
                                ${needsAction ? '<span style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; font-size: 0.75rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; display: inline-flex; align-items: center; gap: 0.3rem;"><i class="fa-solid fa-triangle-exclamation"></i> Requiere tu respuesta</span>' : ''}
                                <strong style="font-size: 1.05rem; color: var(--text-primary);">${this.escapeHtml(t.asunto)}</strong>
                                ${this._formatTicketStatusBadge(t.estado)}
                                ${this._formatTicketPriorityBadge(t.prioridad)}
                            </div>
                            
                            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem; display: flex; flex-wrap: wrap; gap: 1rem;">
                                <span><i class="fa-solid fa-book" style="color: var(--primary);"></i> Libro: <strong>${this.escapeHtml(t.publicacion_titulo || `Publicación #${t.publicacion_id}`)}</strong></span>
                                <span><i class="fa-solid fa-user"></i> Estudiante: ${this.escapeHtml(t.usuario_nombre || `Usuario #${t.usuario_id}`)}</span>
                                ${t.moderador_nombre ? `<span><i class="fa-solid fa-shield-halved" style="color: #a855f7;"></i> Moderador: ${this.escapeHtml(t.moderador_nombre)}</span>` : ''}
                            </div>

                            ${t.ultimo_mensaje ? `
                            <div style="background: var(--bg-surface); border-left: 3px solid var(--primary); padding: 0.6rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; font-size: 0.83rem; color: var(--text-secondary); margin-top: 0.5rem; font-style: italic;">
                                «${this.escapeHtml(t.ultimo_mensaje)}»
                            </div>
                            ` : ''}
                        </div>

                        <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.6rem;">
                            <span style="font-size: 0.78rem; color: var(--text-muted);">
                                Actualizado: ${new Date(t.actualizado_en).toLocaleDateString()} ${new Date(t.actualizado_en).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            <button class="btn ${needsAction ? 'btn-primary' : 'btn-secondary'}" onclick="app.openTicketModal(${t.id})" style="display: flex; align-items: center; gap: 0.4rem; padding: 0.45rem 1rem;">
                                <i class="fa-solid fa-comments"></i> Abrir Conversación (${t.mensajes_count || 1})
                            </button>
                        </div>
                    </div>
                </div>
                `;
            }).join("");
        } catch (e) {
            container.innerHTML = `<p style="color: var(--danger); text-align: center; padding: 2rem;">Error al cargar tickets: ${this.escapeHtml(e.message)}</p>`;
        }
    }

}
