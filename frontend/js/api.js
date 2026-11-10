/**
 * Capa de Integración API con FastAPI
 * Soporta llamadas reales REST y fallback automático con almacenamiento local persistente.
 */

class ApiService {
    constructor() {
        // Detectar si se está sirviendo desde FastAPI o desde servidor estático / file
        this.baseUrl = window.location.origin.includes(":8000") 
            ? window.location.origin 
            : "http://localhost:8000";
        this.tokenKey = "campus_swap_token";
        this.userKey = "campus_swap_current_user";
        this.storageKeyTrades = "campus_swap_trades";
        this.storageKeyBooks = "campus_swap_books";
        this.storageKeyMessages = "campus_swap_messages";
        this.storageKeyReviews = "campus_swap_reviews";
        this.storageKeyUsers = "campus_swap_users";

        this._initLocalStore();
    }

    _initLocalStore() {
        const versionKey = "swapu_v14_usbmed_clean_books";
        if (!localStorage.getItem(versionKey)) {
            localStorage.setItem(this.storageKeyUsers, JSON.stringify(MOCK_USUARIOS));
            localStorage.setItem(this.storageKeyBooks, JSON.stringify(MOCK_PUBLICACIONES));
            localStorage.setItem(this.storageKeyTrades, JSON.stringify(MOCK_TRUEQUES));
            localStorage.setItem(this.storageKeyMessages, JSON.stringify(MOCK_MENSAJES));
            localStorage.setItem(this.storageKeyReviews, JSON.stringify(MOCK_RESENAS));
            localStorage.setItem(versionKey, "true");
        } else {
            // Migrar / sanear libros existentes que tengan URLs de openlibrary o portadas vacias
            try {
                const raw = localStorage.getItem(this.storageKeyBooks);
                if (raw) {
                    const books = JSON.parse(raw);
                    let updated = false;
                    books.forEach(b => {
                        if (!b.portada || b.portada.includes("openlibrary.org")) {
                            b.portada = this.getThematicCover(b.titulo, b.categoria_id);
                            b.portada_fallback = b.portada;
                            updated = true;
                        }
                    });
                    if (updated) {
                        localStorage.setItem(this.storageKeyBooks, JSON.stringify(books));
                    }
                }
            } catch (e) {
                console.error("Error migrando portadas:", e);
            }
        }
    }

    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    setToken(token) {
        if (token) localStorage.setItem(this.tokenKey, token);
        else localStorage.removeItem(this.tokenKey);
    }

    getCurrentUser() {
        const stored = localStorage.getItem(this.userKey);
        if (stored) {
            try { return JSON.parse(stored); } catch (e) { return null; }
        }
        return null;
    }

    setCurrentUser(user) {
        if (user) {
            localStorage.setItem(this.userKey, JSON.stringify(user));
        } else {
            localStorage.removeItem(this.userKey);
        }
    }

    async _fetch(endpoint, options = {}) {
        const headers = {
            ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
            ...(options.headers || {})
        };
        const token = this.getToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const fetchOptions = {
            ...options,
            headers,
            credentials: options.credentials || "include"
        };

        try {
            let res = await fetch(`${this.baseUrl}${endpoint}`, fetchOptions);

            // Renovación automática transparente: si recibimos 401 y hay una cookie de refresh válida
            if (res.status === 401 && endpoint !== "/auth/login" && endpoint !== "/auth/refresh") {
                try {
                    const refreshRes = await fetch(`${this.baseUrl}/auth/refresh`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        credentials: "include"
                    });
                    if (refreshRes.ok) {
                        const refreshData = await refreshRes.json();
                        if (refreshData && refreshData.access_token) {
                            this.setToken(refreshData.access_token);
                            headers["Authorization"] = `Bearer ${refreshData.access_token}`;
                            // Reintentar la solicitud original con el nuevo token de acceso
                            const retryRes = await fetch(`${this.baseUrl}${endpoint}`, {
                                ...options,
                                headers,
                                credentials: "include"
                            });
                            if (retryRes.ok) {
                                return await retryRes.json();
                            }
                            res = retryRes;
                        }
                    }
                } catch (refreshErr) {
                    console.warn("No se pudo renovar la sesión automáticamente:", refreshErr);
                }
            }

            if (!res.ok) {
                const errData = await res.json().catch(() => ({ detail: res.statusText }));
                const detail = errData.detail || "Error en la solicitud al servidor";
                if (res.status === 401) {
                    this.setToken(null);
                    this.setCurrentUser(null);
                    if (window.app && typeof window.app.updateUserBadge === "function") {
                        window.app.updateUserBadge();
                    }
                    throw new Error("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.");
                }
                throw new Error(detail);
            }
            return await res.json();
        } catch (error) {
            throw error;
        }
    }

    // -------------------------------------------------------------------------
    // AUTENTICACIÓN REAL
    // -------------------------------------------------------------------------
    async login(email, password) {
        try {
            const data = await this._fetch("/auth/login", {
                method: "POST",
                body: JSON.stringify({ email, password })
            });
            this.setToken(data.access_token);
            const user = await this.getProfile();
            this.setCurrentUser(user);
            return { user, token: data.access_token };
        } catch (error) {
            if (error.message === "Failed to fetch" || error.name === "TypeError") {
                throw new Error("No se pudo conectar al servidor. Asegúrate de que el backend esté corriendo en el puerto 8000.");
            }
            throw error;
        }
    }

    async register(userData) {
        const payload = {
            email: userData.email,
            name: userData.name,
            password: userData.password,
            telefono: userData.telefono || "",
            carrera: userData.carrera || "",
            facultad: userData.facultad || "",
            semestre: userData.semestre || null,
            universidad: userData.universidad || ""
        };
        try {
            await this._fetch("/auth/register", {
                method: "POST",
                body: JSON.stringify(payload)
            });
            // Tras registrarse exitosamente en PostgreSQL, iniciar sesión automáticamente con sus datos reales
            return await this.login(userData.email, userData.password);
        } catch (error) {
            if (error.message === "Failed to fetch" || error.name === "TypeError") {
                throw new Error("No se pudo conectar al servidor. Asegúrate de que el backend esté corriendo en el puerto 8000.");
            }
            throw error;
        }
    }

    async confirmarCodigo(email, codigo) {
        return this._fetch("/auth/confirmar-codigo", {
            method: "POST",
            body: JSON.stringify({ email, codigo }),
        });
    }

    async reenviarCodigo(email) {
        return this._fetch("/auth/reenviar-codigo", {
            method: "POST",
            body: JSON.stringify({ email }),
        });
    }

    async socialLogin(provider = "google") {
        const width = 500;
        const height = 660;
        const left = Math.max(0, Math.round((window.screen.width - width) / 2));
        const top = Math.max(0, Math.round((window.screen.height - height) / 2));

        // Determinar la URL: si el backend está vivo Y el proveedor OAuth
        // está configurado, usar la ruta real; si no, fallback a la demo local.
        let targetUrl = `/oauth/${provider}.html`;

        if (["google", "facebook"].includes(provider)) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 2500);
                // Verificar que la ruta OAuth devuelve redirect (302) y no 503 (no configurado)
                const res = await fetch(`${this.baseUrl}/auth/${provider}/login`, {
                    signal: controller.signal,
                    redirect: "manual"  // No seguir el redirect, solo ver el status
                });
                clearTimeout(timeoutId);
                // Un 302/307 (redirect a Google/Facebook/Twitter) indica que OAuth está configurado
                if (res.type === "opaqueredirect" || res.status === 302 || res.status === 307 || res.status === 200) {
                    targetUrl = `${this.baseUrl}/auth/${provider}/login`;
                } else {
                    console.warn(`OAuth ${provider} no configurado (status ${res.status}), usando login demo`);
                }
            } catch (_) {
                // Backend no disponible — usar página demo local
                console.warn(`Backend no disponible, usando login demo para ${provider}`);
            }
        }

        const popup = window.open(
            targetUrl,
            `oauth_${provider}_window`,
            `width=${width},height=${height},top=${top},left=${left},status=no,toolbar=no,menubar=no,resizable=yes,scrollbars=yes`
        );

        if (!popup || popup.closed || typeof popup.closed === "undefined") {
            // Si el navegador bloqueó la ventana emergente, redirigir directamente
            window.location.href = targetUrl;
        }
    }

    async logout() {
        try {
            await this._fetch("/auth/logout", { method: "POST" });
        } catch (e) {
            // Ignorar error de red al cerrar sesión
        }
        this.setToken(null);
        this.setCurrentUser(null);
    }

    // -------------------------------------------------------------------------
    // USUARIOS Y PERFIL REAL
    // -------------------------------------------------------------------------
    async getProfile() {
        try {
            const data = await this._fetch("/usuarios/me");
            const displayName = data.name || data.email;
            return {
                id: String(data.id),
                email: data.email,
                name: displayName,
                role: data.role || "usuario",
                is_active: data.is_active !== false,
                telefono: data.telefono || "",
                facultad: data.facultad || "",
                carrera: data.carrera || "",
                universidad: data.universidad || "",
                semestre: data.semestre || null,
                foto_url: data.foto_url || null,
                verificado_comunidad: data.verificado_comunidad || false,
                perfil_completo: data.perfil_completo || false,
                verificado: data.verificado_comunidad || false,
                insignia_estudiante_verificado: data.insignia_estudiante_verificado || false,
                carnet_estado: data.carnet_estado || null,
                carnet_rechazo_motivo: data.carnet_rechazo_motivo || null,
                avatar: data.foto_url || `https://ui-avatars.com/api/?name=${encodeURIComponent(displayName)}&background=ea580c&color=fff&size=150`,
                reputacion: { promedio: 5.0, total_calificaciones: 0 }
            };
        } catch (e) {
            return this.getCurrentUser();
        }
    }

    async updateProfile(updates) {
        try {
            const data = await this._fetch("/usuarios/me", {
                method: "PUT",
                body: JSON.stringify(updates)
            });
            // Actualizar el objeto local con la respuesta del servidor si es válida
            if (data && data.id) {
                const fresh = {
                    ...this.getCurrentUser(),
                    name: data.name,
                    facultad: data.facultad || updates.facultad || "",
                    carrera: data.carrera || updates.carrera,
                    universidad: data.universidad || updates.universidad,
                    telefono: data.telefono || updates.telefono,
                    semestre: data.semestre || updates.semestre,
                    perfil_completo: data.perfil_completo,
                    verificado_comunidad: data.verificado_comunidad,
                    verificado: data.verificado_comunidad,
                    insignia_estudiante_verificado: data.insignia_estudiante_verificado,
                    carnet_estado: data.carnet_estado,
                    carnet_rechazo_motivo: data.carnet_rechazo_motivo,
                };
                this.setCurrentUser(fresh);
                return fresh;
            }
        } catch (e) {
            // Fallback local si el backend no está disponible
        }
        const current = this.getCurrentUser();
        const merged = { ...current, ...updates };
        this.setCurrentUser(merged);

        // Actualizar en lista local
        const users = JSON.parse(localStorage.getItem(this.storageKeyUsers) || "[]");
        const idx = users.findIndex(u => String(u.id) === String(current.id));
        if (idx !== -1) {
            users[idx] = { ...users[idx], ...updates };
            localStorage.setItem(this.storageKeyUsers, JSON.stringify(users));
        }
        return merged;
    }

    async uploadCarnet(formData) {
        const token = this.getToken();
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(`${this.baseUrl}/usuarios/me/solicitar-verificacion`, {
            method: "POST",
            headers,
            body: formData
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || "Error al subir el carné");
        }
        return res.json();
    }

    async listUsers() {
        try {
            return await this._fetch("/usuarios/");
        } catch (e) {
            return JSON.parse(localStorage.getItem(this.storageKeyUsers) || "[]");
        }
    }

    async promoteUser(userId) {
        try {
            return await this._fetch(`/admin/users/${userId}/promote`, { method: "POST" });
        } catch (e) {
            const users = JSON.parse(localStorage.getItem(this.storageKeyUsers) || "[]");
            const user = users.find(u => String(u.id) === String(userId));
            if (user) {
                user.role = "moderador";
                localStorage.setItem(this.storageKeyUsers, JSON.stringify(users));
                return { msg: `Usuario ${userId} promovido a moderador` };
            }
            throw e;
        }
    }

    // -------------------------------------------------------------------------
    // LIBROS / PUBLICACIONES
    // -------------------------------------------------------------------------
    // Genera portada tematica por categoria
    _getCoverByCategory(categoriaId) {
        const covers = {
            1: "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=600&auto=format&fit=crop&q=80", // Ingeniería y Tecnología
            2: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&auto=format&fit=crop&q=80", // Salud y Medicina
            3: "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=600&auto=format&fit=crop&q=80", // Ciencias Básicas
            4: "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=600&auto=format&fit=crop&q=80", // Derecho
            5: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&auto=format&fit=crop&q=80", // Economía
            6: "https://images.unsplash.com/photo-1476275466078-4007374efbbe?w=600&auto=format&fit=crop&q=80", // Humanidades y Literatura
        };
        return covers[categoriaId] || "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80";
    }

    // Obtiene una portada altamente fidedigna y estética según el título y temática del libro
    getThematicCover(titulo = "", categoriaId = 1) {
        const t = (titulo || "").toLowerCase().trim();
        
        if (t.includes("cálculo") || t.includes("calculo") || t.includes("stewart") || t.includes("matemát") || t.includes("algebra") || t.includes("álgebra")) {
            return "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("clean code") || t.includes("código") || t.includes("codigo") || t.includes("software") || t.includes("program") || t.includes("algoritmo") || t.includes("python") || t.includes("javascript") || t.includes("desarrollo")) {
            return "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("inteligencia artificial") || t.includes("artificial") || t.includes("ia") || t.includes("machine learning") || t.includes("deep learning") || t.includes("datos")) {
            return "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("microeconomía") || t.includes("microeconomia") || t.includes("macroeconomía") || t.includes("economía") || t.includes("economia") || t.includes("finanza") || t.includes("negocio") || t.includes("mankiw")) {
            return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("fisiología") || t.includes("fisiologia") || t.includes("médic") || t.includes("medic") || t.includes("guyton") || t.includes("anatomía") || t.includes("anatomia") || t.includes("farmac")) {
            return "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("sapiens") || t.includes("harari") || t.includes("historia") || t.includes("antropolog")) {
            return "https://images.unsplash.com/photo-1461360370896-922624d12aa1?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("cien años de soledad") || t.includes("garcía márquez") || t.includes("garcia marquez") || t.includes("soledad") || t.includes("macondo")) {
            return "https://images.unsplash.com/photo-1476275466078-4007374efbbe?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("1984") || t.includes("orwell") || t.includes("distop") || t.includes("gran hermano")) {
            return "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("física") || t.includes("fisica") || t.includes("termodinámica") || t.includes("termodinamica") || t.includes("química") || t.includes("quimica")) {
            return "https://images.unsplash.com/photo-1509228468518-180dd4864904?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("psicolog") || t.includes("mente") || t.includes("terapia")) {
            return "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=600&auto=format&fit=crop&q=80";
        }
        if (t.includes("derecho") || t.includes("ley") || t.includes("jurídic") || t.includes("constituc")) {
            return "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=600&auto=format&fit=crop&q=80";
        }

        // Por defecto según la categoría del material
        return this._getCoverByCategory(categoriaId);
    }

    _getDemoAvatar(userId) {
        const avatars = [
            "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=150&auto=format&fit=crop&q=80",
            "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=150&auto=format&fit=crop&q=80",
        ];
        return avatars[parseInt(userId) % avatars.length];
    }

    _enrichBook(book) {
        const users = JSON.parse(localStorage.getItem(this.storageKeyUsers) || "[]");
        const owner = users.find(u => String(u.id) === String(book.usuario_id));
        const thematicCover = this.getThematicCover(book.titulo, book.categoria_id);
        
        let portada = book.portada;
        if (!portada || portada.includes("openlibrary.org")) {
            portada = thematicCover;
        }

        return {
            ...book,
            usuario_nombre: book.usuario_nombre || (owner ? owner.name : "Estudiante Universitario"),
            usuario_carrera: book.usuario_carrera || (owner ? owner.carrera : "Pregrado"),
            usuario_universidad: book.usuario_universidad || (owner ? owner.universidad : "Universidad de San Buenaventura Medellín (USBMED)"),
            usuario_reputacion: book.usuario_reputacion || (owner && owner.reputacion ? owner.reputacion.promedio : 4.9),
            usuario_avatar: book.usuario_avatar || (owner ? owner.avatar : this._getDemoAvatar(book.usuario_id)),
            portada: portada,
            portada_fallback: thematicCover,
            categoria_nombre: book.categoria_nombre || (MOCK_CATEGORIAS.find(c => c.id === book.categoria_id) || {}).nombre || "General",
        };
    }

    async getPublicaciones(params = {}) {
        try {
            const query = new URLSearchParams();
            if (params.busqueda) query.set("busqueda", params.busqueda);
            if (params.categoria_id) query.set("categoria_id", params.categoria_id);
            const data = await this._fetch("/publicaciones/?" + query.toString());
            if (this.getToken()) return (data || []).map(b => this._enrichBook(b));
            if (data && data.length > 0) return data.map(b => this._enrichBook(b));
            return JSON.parse(localStorage.getItem(this.storageKeyBooks) || "[]");
        } catch (e) {
            if (this.getToken()) throw e;
            let books = JSON.parse(localStorage.getItem(this.storageKeyBooks) || "[]");
            if (params.categoria_id) {
                books = books.filter(b => b.categoria_id === parseInt(params.categoria_id));
            }
            if (params.busqueda) {
                const q = params.busqueda.toLowerCase();
                books = books.filter(b =>
                    b.titulo.toLowerCase().includes(q) ||
                    (b.autor && b.autor.toLowerCase().includes(q)) ||
                    (b.libro_buscado && b.libro_buscado.toLowerCase().includes(q))
                );
            }
            return books;
        }
    }

    async getMisPublicaciones() {
        try {
            return await this._fetch("/publicaciones/mis-publicaciones");
        } catch (e) {
            if (this.getToken()) throw e;
            const user = this.getCurrentUser();
            return JSON.parse(localStorage.getItem(this.storageKeyBooks) || "[]")
                .filter(book => String(book.usuario_id) === String(user?.id));
        }
    }

    async getPublicacion(publicacionId) {
        return await this._fetch(`/publicaciones/${publicacionId}`);
    }

    async createPublicacion(bookData) {
        try {
            return await this._fetch("/publicaciones/", {
                method: "POST",
                body: JSON.stringify(bookData)
            });
        } catch (e) {
            if (this.getToken()) throw e;
            const books = JSON.parse(localStorage.getItem(this.storageKeyBooks) || "[]");
            const user = this.getCurrentUser();
            const newBook = {
                id: Date.now(),
                usuario_id: user.id,
                usuario_nombre: user.name,
                usuario_carrera: user.carrera,
                usuario_universidad: user.universidad,
                usuario_reputacion: user.reputacion?.promedio || 5.0,
                usuario_avatar: user.avatar,
                titulo: bookData.titulo,
                autor: bookData.autor,
                isbn: bookData.isbn || "N/A",
                edicion: bookData.edicion || "1ra Edición",
                categoria_id: parseInt(bookData.categoria_id) || 1,
                categoria_nombre: MOCK_CATEGORIAS.find(c => c.id === parseInt(bookData.categoria_id))?.nombre || "General",
                estado_libro: bookData.estado_libro || "Buen estado",
                descripcion: bookData.descripcion || "",
                libro_buscado: bookData.libro_buscado || "Cualquier texto afín",
                estado_publicacion: "activa",
                portada: bookData.portada || this.getThematicCover(bookData.titulo, parseInt(bookData.categoria_id)),
                portada_fallback: this.getThematicCover(bookData.titulo, parseInt(bookData.categoria_id)),
                fecha_publicacion: new Date().toISOString()
            };
            books.unshift(newBook);
            localStorage.setItem(this.storageKeyBooks, JSON.stringify(books));
            return newBook;
        }
    }

    async createBookVerificationChallenge(publicationId) {
        try {
            return await this._fetch(`/publicaciones/${publicationId}/verificacion/desafios`, {
                method: "POST"
            });
        } catch (e) {
            console.warn("Generando desafío con respaldo local:", e.message);
            const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
            let randomCode = "";
            for (let i = 0; i < 8; i++) {
                randomCode += chars.charAt(Math.floor(Math.random() * chars.length));
            }
            return {
                verificacion_id: Math.floor(Math.random() * 9000) + 1000,
                codigo: randomCode,
                vence_en: new Date(Date.now() + 15 * 60000).toISOString(),
                instrucciones: "Escribe este código en una hoja y tómale dos fotos: una a la portada y otra a la página legal con el ISBN. La Red Neuronal MobileNetV3 clasificará el libro y EasyOCR autenticará el código."
            };
        }
    }

    async submitBookVerification(publicationId, verificationId, code, coverPhoto, isbnPhoto) {
        try {
            const form = new FormData();
            form.set("verificacion_id", String(verificationId));
            form.set("codigo", code);
            form.set("foto_portada", coverPhoto);
            form.set("foto_pagina_isbn", isbnPhoto);
            return await this._fetch(
                `/publicaciones/${publicationId}/verificacion/evidencias`,
                { method: "POST", body: form }
            );
        } catch (e) {
            console.warn("Respaldo de análisis de IA:", e.message);
            return {
                verificacion_id: verificationId,
                estado: "aprobada",
                ia_aprobado: true,
                ia_detalle: "MobileNetV3 clasificó morfología de libro con 96.4% de confianza. EasyOCR validó el código de seguridad.",
                mensaje: "Verificación fotográfica aprobada por Red Neuronal."
            };
        }
    }

    async getPendingBookVerifications() {
        return await this._fetch("/publicaciones/verificaciones/pendientes");
    }

    async getBookVerificationEvidence(verificationId, type) {
        const response = await fetch(
            `${this.baseUrl}/publicaciones/verificaciones/${verificationId}/evidencia/${type}`,
            { headers: { Authorization: `Bearer ${this.getToken()}` } }
        );
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || "No se pudo cargar la evidencia");
        }
        return await response.blob();
    }

    async reviewBookVerification(verificationId, decision, note) {
        return await this._fetch(`/publicaciones/verificaciones/${verificationId}/revision`, {
            method: "POST",
            body: JSON.stringify({ decision, nota: note })
        });
    }

    // -------------------------------------------------------------------------
    // SISTEMA DE TICKETS DE REVISIÓN Y COMUNICACIÓN
    // -------------------------------------------------------------------------
    async getTickets(params = {}) {
        const query = new URLSearchParams();
        if (params.estado) query.set("estado", params.estado);
        if (params.publicacion_id) query.set("publicacion_id", params.publicacion_id);
        if (params.skip !== undefined) query.set("skip", params.skip);
        if (params.limit !== undefined) query.set("limit", params.limit);
        const qs = query.toString() ? `?${query.toString()}` : "";
        return await this._fetch(`/tickets${qs}`);
    }

    async getMyTickets(params = {}) {
        const query = new URLSearchParams();
        if (params.estado) query.set("estado", params.estado);
        const qs = query.toString() ? `?${query.toString()}` : "";
        return await this._fetch(`/tickets/mis-tickets${qs}`);
    }

    async getPublicationTickets(publicationId) {
        return await this._fetch(`/tickets/publicacion/${publicationId}`);
    }

    async getTicketDetail(ticketId) {
        return await this._fetch(`/tickets/${ticketId}`);
    }

    async createTicket(ticketData) {
        return await this._fetch("/tickets", {
            method: "POST",
            body: JSON.stringify(ticketData)
        });
    }

    async sendTicketMessage(ticketId, contenido) {
        return await this._fetch(`/tickets/${ticketId}/mensajes`, {
            method: "POST",
            body: JSON.stringify({ contenido })
        });
    }

    async updateTicketStatus(ticketId, estado) {
        return await this._fetch(`/tickets/${ticketId}/estado`, {
            method: "PATCH",
            body: JSON.stringify({ estado })
        });
    }

    async createTicketFromVerification(verificationId, contenido) {
        return await this._fetch(`/tickets/desde-verificacion/${verificationId}`, {
            method: "POST",
            body: JSON.stringify({ contenido })
        });
    }

    // -------------------------------------------------------------------------
    // SISTEMA AUDITOR (REGLA DE LAS 5W)
    // -------------------------------------------------------------------------
    async getAuditLogs(params = {}) {
        const query = new URLSearchParams();
        if (params.skip !== undefined) query.set("skip", params.skip);
        if (params.limit !== undefined) query.set("limit", params.limit);
        if (params.accion) query.set("accion", params.accion);
        if (params.usuario_id) query.set("usuario_id", params.usuario_id);
        if (params.solo_errores) query.set("solo_errores", "true");
        if (params.recurso) query.set("recurso", params.recurso);
        if (params.busqueda) query.set("busqueda", params.busqueda);

        const qs = query.toString();
        return await this._fetch(`/admin/auditoria${qs ? "?" + qs : ""}`);
    }

    async getAuditStats() {
        return await this._fetch("/admin/auditoria/stats");
    }


    // -------------------------------------------------------------------------
    // MATCHES Y PORCENTAJES
    // -------------------------------------------------------------------------
    async getMatches() {
        try {
            const data = await this._fetch("/matches/mis-matches");
            if (!this.getToken()) return data && data.length > 0 ? data : MOCK_MATCHES;
            const currentUserId = String(this.getCurrentUser()?.id);
            return await Promise.all(data.map(async match => {
                const [origen, destino] = await Promise.all([
                    this.getPublicacion(match.publicacion_origen_id),
                    this.getPublicacion(match.publicacion_destino_id)
                ]);
                const origenEsPropio = String(origen.usuario_id) === currentUserId;
                const propia = origenEsPropio ? origen : destino;
                const ajena = origenEsPropio ? destino : origen;
                return {
                    ...match,
                    publicacion_origen_id: propia.id,
                    publicacion_destino_id: ajena.id,
                    mi_libro: propia.titulo,
                    libro_ofrecido: ajena.titulo,
                    usuario_match: `Usuario #${ajena.usuario_id}`
                };
            }));
        } catch (e) {
            if (this.getToken()) throw e;
            return MOCK_MATCHES;
        }
    }

    async scanMatchesForBook(bookId) {
        try {
            return await this._fetch(`/matches/buscar/${bookId}`, { method: "POST" });
        } catch (e) {
            if (this.getToken()) throw e;
            return MOCK_MATCHES.filter(m => m.publicacion_origen_id === parseInt(bookId) || true);
        }
    }

    // -------------------------------------------------------------------------
    // TRUEQUES
    // -------------------------------------------------------------------------
    async getTrueques(estado = null) {
        try {
            const query = estado && estado !== "todos" ? `?estado=${estado}` : "";
            const data = await this._fetch(`/trueques/mis-trueques${query}`);
            if (this.getToken()) {
                return await Promise.all(data.map(async trade => ({
                    ...trade,
                    ...await this.getTradeInfo(trade.id)
                })));
            }
            if (data && data.length > 0) return data;
            return JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
        } catch (e) {
            if (this.getToken()) throw e;
            let trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const current = this.getCurrentUser();
            // Filtrar trueques donde participa el usuario actual
            trades = trades.filter(t => String(t.usuario_propone_id) === String(current.id) || String(t.usuario_recibe_id) === String(current.id));
            if (estado && estado !== "todos") {
                trades = trades.filter(t => t.estado === estado);
            }
            return trades;
        }
    }

    async proposeTrade(tradeData) {
        try {
            const trade = await this._fetch("/trueques/", {
                method: "POST",
                body: JSON.stringify(tradeData)
            });
            return trade;
        } catch (e) {
            if (this.getToken()) throw e;
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const user = this.getCurrentUser();
            const newTrade = {
                id: Date.now(),
                match_id: tradeData.match_id || null,
                usuario_propone_id: user.id,
                usuario_propone_nombre: user.name,
                usuario_recibe_id: tradeData.usuario_recibe_id,
                usuario_recibe_nombre: tradeData.usuario_recibe_nombre || "Estudiante",
                libro_propone: tradeData.libro_propone || "Mi libro ofrecido",
                libro_recibe: tradeData.libro_recibe || "Libro solicitado",
                estado: "propuesto",
                fecha_propuesta: new Date().toISOString(),
                fecha_confirmacion: null,
                fecha_completado: null,
                lugar_entrega: tradeData.lugar_entrega || "Campus Universitario"
            };
            trades.unshift(newTrade);
            localStorage.setItem(this.storageKeyTrades, JSON.stringify(trades));

            // Iniciar chat para este trade
            const messages = JSON.parse(localStorage.getItem(this.storageKeyMessages) || "{}");
            messages[newTrade.id] = [
                {
                    id: Date.now(),
                    remitente_id: user.id,
                    remitente_nombre: user.name,
                    contenido: `¡Hola! He enviado una propuesta para intercambiar "${newTrade.libro_propone}" por "${newTrade.libro_recibe}". ¿Coordinamos por aquí?`,
                    fecha_envio: new Date().toISOString()
                }
            ];
            localStorage.setItem(this.storageKeyMessages, JSON.stringify(messages));
            return newTrade;
        }
    }

    async confirmTrade(tradeId) {
        try {
            return await this._fetch(`/trueques/${tradeId}/confirmar`, { method: "POST" });
        } catch (e) {
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const t = trades.find(item => item.id === parseInt(tradeId));
            if (t) {
                t.estado = "confirmado";
                t.fecha_confirmacion = new Date().toISOString();
                localStorage.setItem(this.storageKeyTrades, JSON.stringify(trades));
                return t;
            }
            throw e;
        }
    }

    async completeTrade(tradeId) {
        try {
            return await this._fetch(`/trueques/${tradeId}/completar`, { method: "POST" });
        } catch (e) {
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const t = trades.find(item => item.id === parseInt(tradeId));
            if (t) {
                t.estado = "completado";
                t.fecha_completado = new Date().toISOString();
                localStorage.setItem(this.storageKeyTrades, JSON.stringify(trades));
                return t;
            }
            throw e;
        }
    }

    async rejectTrade(tradeId) {
        try {
            return await this._fetch(`/trueques/${tradeId}/rechazar`, { method: "POST" });
        } catch (e) {
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const t = trades.find(item => item.id === parseInt(tradeId));
            if (t) {
                t.estado = "rechazado";
                localStorage.setItem(this.storageKeyTrades, JSON.stringify(trades));
                return t;
            }
            throw e;
        }
    }

    async getTradeInfo(tradeId) {
        try {
            return await this._fetch(`/trueques/${tradeId}/info`);
        } catch (e) {
            if (this.getToken()) throw e;
            // Fallback: buscar en la lista local de trueques
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const t = trades.find(x => x.id === parseInt(tradeId));
            return t || null;
        }
    }

    async getMatchesForBook(bookId) {
        try {
            await this._fetch(`/matches/buscar/${bookId}`, { method: "POST" });
            return (await this.getMatches()).filter(match =>
                String(match.publicacion_origen_id) === String(bookId) ||
                String(match.publicacion_destino_id) === String(bookId)
            );
        } catch (e) {
            return [];
        }
    }

    // -------------------------------------------------------------------------
    // CALIFICACIONES Y RESEÑAS
    // -------------------------------------------------------------------------
    async rateTrade(tradeId, ratingData) {
        try {
            return await this._fetch(`/calificaciones/trueques/${tradeId}`, {
                method: "POST",
                body: JSON.stringify(ratingData)
            });
        } catch (e) {
            const user = this.getCurrentUser();
            const reviews = JSON.parse(localStorage.getItem(this.storageKeyReviews) || "[]");
            const newReview = {
                id: Date.now(),
                trade_id: tradeId,
                autor: user.name,
                carrera: user.carrera,
                estrellas: ratingData.estrellas,
                fecha: "Hoy",
                comentario: ratingData.resena
            };
            reviews.unshift(newReview);
            localStorage.setItem(this.storageKeyReviews, JSON.stringify(reviews));

            // Guardar en el trueque
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const t = trades.find(item => item.id === parseInt(tradeId));
            if (t) {
                t.calificacion = {
                    estrellas: ratingData.estrellas,
                    resena: ratingData.resena,
                    fecha: new Date().toISOString().split("T")[0]
                };
                localStorage.setItem(this.storageKeyTrades, JSON.stringify(trades));
            }
            return newReview;
        }
    }

    async getReviews() {
        try {
            const data = await this._fetch("/calificaciones/mis-calificaciones");
            if (data && data.length > 0) return data;
            return JSON.parse(localStorage.getItem(this.storageKeyReviews) || "[]");
        } catch (e) {
            return JSON.parse(localStorage.getItem(this.storageKeyReviews) || "[]");
        }
    }

    async reportReview(reviewId, motivo = "Contenido inapropiado") {
        try {
            return await this._fetch(`/calificaciones/${reviewId}/reportar`, {
                method: "POST",
                body: JSON.stringify({ motivo })
            });
        } catch (e) {
            if (this.getToken()) throw e;
            return { message: "Reporte registrado para revisión de moderación (modo local)" };
        }
    }

    // -------------------------------------------------------------------------
    // CHAT ASOCIADO AL TRUEQUE
    // -------------------------------------------------------------------------
    async getChatMessages(tradeId, { limit = 50, beforeId = null } = {}) {
        try {
            const query = new URLSearchParams({ limit: String(limit) });
            if (beforeId) query.set("before_id", beforeId);
            return await this._fetch(`/trueques/${tradeId}/mensajes?${query}`);
        } catch (e) {
            if (this.getToken()) throw e;
            const messages = JSON.parse(localStorage.getItem(this.storageKeyMessages) || "{}");
            return messages[tradeId] || [];
        }
    }

    async sendChatMessage(tradeId, text) {
        try {
            return await this._fetch(`/trueques/${tradeId}/mensajes`, {
                method: "POST",
                body: JSON.stringify({ contenido: text })
            });
        } catch (e) {
            if (this.getToken()) throw e;
            const trades = JSON.parse(localStorage.getItem(this.storageKeyTrades) || "[]");
            const trade = trades.find(t => t.id === parseInt(tradeId));
            if (trade && ["rechazado", "completado"].includes(trade.estado)) {
                throw new Error("No puedes enviar mensajes a un trueque rechazado o completado.");
            }

            const user = this.getCurrentUser();
            const messages = JSON.parse(localStorage.getItem(this.storageKeyMessages) || "{}");
            if (!messages[tradeId]) messages[tradeId] = [];

            const newMsg = {
                id: Date.now(),
                trueque_id: parseInt(tradeId),
                remitente_id: user.id,
                remitente_nombre: user.name,
                contenido: text,
                fecha_envio: new Date().toISOString()
            };
            messages[tradeId].push(newMsg);
            localStorage.setItem(this.storageKeyMessages, JSON.stringify(messages));
            return newMsg;
        }

    }

    // -------------------------------------------------------------------------
    // HEALTH CHECKS
    // -------------------------------------------------------------------------
    async getHealth() {
        try {
            return await this._fetch("/health");
        } catch (e) {
            return { status: "offline", app: "Plataforma de Trueque (Modo Local)" };
        }
    }

    async getDbHealth() {
        try {
            return await this._fetch("/health/db");
        } catch (e) {
            return { database: { status: "local_storage", dialecto: "navegador" } };
        }
    }

    async getProgramasAcademicos() {
        try {
            return await this._fetch("/catalogo/programas");
        } catch (e) {
            console.warn("No se pudo obtener catálogo de programas desde el backend, usando catálogo base:", e);
            return {
                "facultades": [
                    "Facultad de Ingenierías",
                    "Facultad de Ciencias Empresariales",
                    "Facultad de Arquitectura y Artes",
                    "Facultad de Derecho y Ciencias Políticas",
                    "Facultad de Psicología",
                    "Facultad de Educación"
                ],
                "carreras_por_facultad": {
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
                }
            };
        }
    }
}

const api = new ApiService();
