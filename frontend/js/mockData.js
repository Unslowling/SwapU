/**
 * Mock data para SwapU — Plataforma de Intercambio de Libros entre Estudiantes.
 */

const MOCK_USUARIOS = [
    {
        id: "1",
        email: "sofia.ramirez@usbmed.edu.co",
        name: "Sofía Ramírez",
        role: "usuario",
        is_active: true,
        telefono: "+57 312 456 7890",
        carrera: "Psicología",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.9,
            total_calificaciones: 18,
            distribucion: { 5: 16, 4: 2, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 14,
        fecha_registro: "2024-02-10"
    },
    {
        id: "2",
        email: "andres.herrera@usbmed.edu.co",
        name: "Andrés Herrera",
        role: "usuario",
        is_active: true,
        telefono: "+57 301 987 6543",
        carrera: "Ingeniería de Sistemas",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.8,
            total_calificaciones: 12,
            distribucion: { 5: 10, 4: 2, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 9,
        fecha_registro: "2024-03-15"
    },
    {
        id: "3",
        email: "camila.torres@usbmed.edu.co",
        name: "Camila Torres",
        role: "moderador",
        is_active: true,
        telefono: "+57 315 222 3344",
        carrera: "Derecho",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 5.0,
            total_calificaciones: 8,
            distribucion: { 5: 8, 4: 0, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 7,
        fecha_registro: "2024-01-20"
    },
    {
        id: "4",
        email: "admin@swapu.co",
        name: "Administrador SwapU",
        role: "admin",
        is_active: true,
        telefono: "+57 300 000 0001",
        carrera: "Gestión de Plataformas",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 5.0,
            total_calificaciones: 35,
            distribucion: { 5: 35, 4: 0, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 25,
        fecha_registro: "2023-11-01"
    },
    {
        id: "5",
        email: "miguel.ospina@usbmed.edu.co",
        name: "Miguel Ospina",
        role: "usuario",
        is_active: true,
        telefono: "+57 320 111 4455",
        carrera: "Psicología",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.7,
            total_calificaciones: 10,
            distribucion: { 5: 7, 4: 3, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 6,
        fecha_registro: "2024-04-01"
    },
    {
        id: "6",
        email: "laura.velez@usbmed.edu.co",
        name: "Laura Vélez",
        role: "usuario",
        is_active: true,
        telefono: "+57 318 777 2233",
        carrera: "Administración de Negocios",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.8,
            total_calificaciones: 8,
            distribucion: { 5: 6, 4: 2, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 5,
        fecha_registro: "2024-05-15"
    },
    {
        id: "7",
        email: "mateo.restrepo@usbmed.edu.co",
        name: "Mateo Restrepo",
        role: "usuario",
        is_active: true,
        telefono: "+57 300 444 8899",
        carrera: "Ingeniería de Datos y Software",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.9,
            total_calificaciones: 15,
            distribucion: { 5: 14, 4: 1, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 11,
        fecha_registro: "2024-03-20"
    },
    {
        id: "8",
        email: "valentina.duarte@usbmed.edu.co",
        name: "Valentina Duarte",
        role: "usuario",
        is_active: true,
        telefono: "+57 311 234 5678",
        carrera: "Ingeniería de Datos y Software",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 5.0,
            total_calificaciones: 9,
            distribucion: { 5: 9, 4: 0, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 8,
        fecha_registro: "2024-02-18"
    },
    {
        id: "9",
        email: "santiago.castro@usbmed.edu.co",
        name: "Santiago Castro",
        role: "usuario",
        is_active: true,
        telefono: "+57 314 888 9900",
        carrera: "Creación de Contenidos Digitales",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.8,
            total_calificaciones: 14,
            distribucion: { 5: 11, 4: 3, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 12,
        fecha_registro: "2024-01-10"
    },
    {
        id: "10",
        email: "mariana.restrepo@usbmed.edu.co",
        name: "Mariana Restrepo",
        role: "usuario",
        is_active: true,
        telefono: "+57 305 666 7711",
        carrera: "Derecho",
        universidad: "Universidad de San Buenaventura Medellín (USBMED)",
        avatar: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=150&auto=format&fit=crop&q=80",
        verificado: true,
        reputacion: {
            promedio: 4.9,
            total_calificaciones: 16,
            distribucion: { 5: 14, 4: 2, 3: 0, 2: 0, 1: 0 }
        },
        trueques_completados: 13,
        fecha_registro: "2024-02-05"
    }
];

const MOCK_CATEGORIAS = [
    { id: 1, nombre: "Ingeniería y Tecnología" },
    { id: 2, nombre: "Ciencias de la Salud y Psicología" },
    { id: 3, nombre: "Ciencias Básicas (Matemáticas, Física)" },
    { id: 4, nombre: "Derecho y Ciencias Políticas" },
    { id: 5, nombre: "Ciencias Económicas y Administrativas" },
    { id: 6, nombre: "Educación, Artes y Humanidades" }
];

const MOCK_PUBLICACIONES = [
    {
        id: 1,
        usuario_id: "2",
        usuario_nombre: "Andrés Herrera",
        usuario_carrera: "Ingeniería de Sistemas",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus Salento)",
        usuario_reputacion: 4.8,
        usuario_avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        titulo: "Cálculo: Trascendentes Tempranas",
        autor: "James Stewart",
        isbn: "978-0538497909",
        edicion: "8va Edición",
        categoria_id: 3,
        categoria_nombre: "Ciencias Básicas",
        estado_libro: "Como nuevo",
        descripcion: "Libro de cálculo diferencial e integral, pasta dura, sin anotaciones ni hojas dobladas. Entrega disponible en Campus Salento (Bello) de la USBMED.",
        libro_buscado: "Clean Code o Algoritmos en Python",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1509228468518-180dd4864904?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:00:00Z"
    },
    {
        id: 2,
        usuario_id: "7",
        usuario_nombre: "Mateo Restrepo",
        usuario_carrera: "Ingeniería de Datos y Software",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus Salento)",
        usuario_reputacion: 4.9,
        usuario_avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        titulo: "Clean Code: Manual de Desarrollo Ágil",
        autor: "Robert C. Martin (Uncle Bob)",
        isbn: "978-0132350884",
        edicion: "1ra Edición en Español",
        categoria_id: 1,
        categoria_nombre: "Ingeniería y Tecnología",
        estado_libro: "Excelente estado",
        descripcion: "El clásico indiscutible sobre buenas prácticas de código limpio, refactorización y testing. USBMED Campus Salento.",
        libro_buscado: "Inteligencia Artificial o Microeconomía",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:05:00Z"
    },
    {
        id: 3,
        usuario_id: "8",
        usuario_nombre: "Valentina Duarte",
        usuario_carrera: "Ingeniería de Datos y Software",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus Salento)",
        usuario_reputacion: 5.0,
        usuario_avatar: "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80",
        titulo: "Inteligencia Artificial: Un Enfoque Moderno",
        autor: "Stuart Russell y Peter Norvig",
        isbn: "978-0134610993",
        edicion: "4ta Edición",
        categoria_id: 1,
        categoria_nombre: "Ingeniería y Tecnología",
        estado_libro: "Como nuevo",
        descripcion: "Referencia fundamental en IA moderna, redes neuronales, búsqueda heurística y aprendizaje automático. USBMED Campus Salento.",
        libro_buscado: "Deep Learning de Ian Goodfellow",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:10:00Z"
    },
    {
        id: 4,
        usuario_id: "6",
        usuario_nombre: "Laura Vélez",
        usuario_carrera: "Administración de Negocios",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus San Benito)",
        usuario_reputacion: 4.8,
        usuario_avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
        titulo: "Principios de Microeconomía",
        autor: "N. Gregory Mankiw",
        isbn: "978-1305971493",
        edicion: "8va Edición",
        categoria_id: 5,
        categoria_nombre: "Ciencias Económicas y Administrativas",
        estado_libro: "Buen estado",
        descripcion: "Fundamentos claros de teoría del consumidor, estructuras de mercado y microeconomía aplicada. USBMED Campus San Benito.",
        libro_buscado: "Macroeconomía o Finanzas Corporativas",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:15:00Z"
    },
    {
        id: 5,
        usuario_id: "5",
        usuario_nombre: "Miguel Ospina",
        usuario_carrera: "Psicología",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus San Benito)",
        usuario_reputacion: 4.7,
        usuario_avatar: "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=150&auto=format&fit=crop&q=80",
        titulo: "Tratado de Fisiología Médica",
        autor: "Arthur C. Guyton & John E. Hall",
        isbn: "978-1455770052",
        edicion: "13va Edición",
        categoria_id: 2,
        categoria_nombre: "Ciencias de la Salud y Psicología",
        estado_libro: "Como nuevo",
        descripcion: "Texto médico insustituible sobre fisiología de sistemas, cardiovascular, renal y nervioso. USBMED Campus San Benito.",
        libro_buscado: "Neuropsicología o Psicometría",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1532938911079-1b06ac7ceec7?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:20:00Z"
    },
    {
        id: 6,
        usuario_id: "1",
        usuario_nombre: "Sofía Ramírez",
        usuario_carrera: "Psicología",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus San Benito)",
        usuario_reputacion: 4.9,
        usuario_avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80",
        titulo: "Sapiens: De animales a dioses",
        autor: "Yuval Noah Harari",
        isbn: "978-0062316097",
        edicion: "Edición Internacional",
        categoria_id: 6,
        categoria_nombre: "Educación, Artes y Humanidades",
        estado_libro: "Excelente estado",
        descripcion: "Breve historia de la humanidad, desde la revolución cognitiva hasta la era biotecnológica. USBMED Campus San Benito.",
        libro_buscado: "Homo Deus o El Hombre en Busca de Sentido",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1461360370896-922624d12aa1?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:25:00Z"
    },
    {
        id: 7,
        usuario_id: "9",
        usuario_nombre: "Santiago Castro",
        usuario_carrera: "Creación de Contenidos Digitales",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus Salento)",
        usuario_reputacion: 4.8,
        usuario_avatar: "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=150&auto=format&fit=crop&q=80",
        titulo: "Cien Años de Soledad",
        autor: "Gabriel García Márquez",
        isbn: "978-0307474728",
        edicion: "Edición Conmemorativa",
        categoria_id: 6,
        categoria_nombre: "Educación, Artes y Humanidades",
        estado_libro: "Nuevo",
        descripcion: "Obra cumbre de la literatura en español y el realismo mágico latinoamericano. USBMED Campus Salento.",
        libro_buscado: "Rayuela de Cortázar o Pedro Páramo",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1476275466078-4007374efbbe?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1474932430478-367dbb6832c1?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:30:00Z"
    },
    {
        id: 8,
        usuario_id: "10",
        usuario_nombre: "Mariana Restrepo",
        usuario_carrera: "Derecho",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus San Benito)",
        usuario_reputacion: 4.9,
        usuario_avatar: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=150&auto=format&fit=crop&q=80",
        titulo: "1984",
        autor: "George Orwell",
        isbn: "978-0451524935",
        edicion: "Edición Especial",
        categoria_id: 6,
        categoria_nombre: "Educación, Artes y Humanidades",
        estado_libro: "Como nuevo",
        descripcion: "Clásico distópico sobre el Gran Hermano, la vigilancia masiva y el control del pensamiento. USBMED Campus San Benito.",
        libro_buscado: "Un Mundo Feliz de Aldous Huxley o Fahrenheit 451",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:35:00Z"
    },
    {
        id: 9,
        usuario_id: "2",
        usuario_nombre: "Felipe Arango",
        usuario_carrera: "Ingeniería Industrial",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus Salento)",
        usuario_reputacion: 4.9,
        usuario_avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
        titulo: "Física Universitaria con Física Moderna",
        autor: "Sears, Zemansky, Young & Freedman",
        isbn: "978-6073221900",
        edicion: "13va Edición",
        categoria_id: 3,
        categoria_nombre: "Ciencias Básicas (Matemáticas, Física)",
        estado_libro: "Excelente estado",
        descripcion: "Fundamentos de mecánica clásica, electromagnetismo, óptica y física cuántica moderna. USBMED Campus Salento.",
        libro_buscado: "Cálculo Multivariable o Ecuaciones Diferenciales",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1509228468518-180dd4864904?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:40:00Z"
    },
    {
        id: 10,
        usuario_id: "3",
        usuario_nombre: "Camila Torres",
        usuario_carrera: "Derecho",
        usuario_universidad: "Universidad de San Buenaventura Medellín (Campus San Benito)",
        usuario_reputacion: 5.0,
        usuario_avatar: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=150&auto=format&fit=crop&q=80",
        titulo: "Teoría General del Derecho",
        autor: "Norberto Bobbio",
        isbn: "978-9583506178",
        edicion: "3ra Edición Revisada",
        categoria_id: 4,
        categoria_nombre: "Derecho y Ciencias Políticas",
        estado_libro: "Como nuevo",
        descripcion: "Filosofía del derecho, validez de la norma y ordenamiento jurídico. Indispensable en la facultad de Derecho USBMED.",
        libro_buscado: "Derecho Constitucional Colombiano",
        estado_publicacion: "activa",
        portada: "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?w=600&auto=format&fit=crop&q=80",
        portada_fallback: "https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=600&auto=format&fit=crop&q=80",
        fecha_publicacion: "2026-10-27T12:45:00Z"
    }
];

const MOCK_MATCHES = [
    {
        id: 1,
        publicacion_origen_id: 1,
        mi_libro: "Cálculo: Trascendentes Tempranas (Stewart)",
        libro_ofrecido: "Estructuras de Datos y Algoritmos en C++",
        usuario_match: "Felipe Arango",
        carrera: "Ingeniería de Sistemas",
        universidad: "UPB",
        avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80",
        tipo_match: "Exacto Bidireccional",
        puntuacion: 98.5,
        motivo: "El libro ofertado coincide con tu búsqueda exacta y Felipe busca tu libro de Cálculo.",
        fecha_creacion: "2026-09-28T12:00:00Z"
    },
    {
        id: 2,
        publicacion_origen_id: 2,
        mi_libro: "Neuropsicología Humana (Kolb & Whishaw)",
        libro_ofrecido: "Manual Diagnóstico y Estadístico DSM-5",
        usuario_match: "Valeria Muñoz",
        carrera: "Psicología",
        universidad: "Universidad de Medellín",
        avatar: "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150&auto=format&fit=crop&q=80",
        tipo_match: "Alta Coincidencia",
        puntuacion: 92.0,
        motivo: "Coincidencia temática en Ciencias de la Salud del mismo bloque curricular.",
        fecha_creacion: "2026-09-28T14:30:00Z"
    },
    {
        id: 3,
        publicacion_origen_id: 5,
        mi_libro: "Inteligencia Artificial: Un Enfoque Moderno",
        libro_ofrecido: "Redes y Cloud Computing — Tanenbaum",
        usuario_match: "Juan Diego Cano",
        carrera: "Ing. de Sistemas",
        universidad: "Universidad Nacional",
        avatar: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150&auto=format&fit=crop&q=80",
        tipo_match: "Coincidencia de Área",
        puntuacion: 85.0,
        motivo: "Facultad de Ingeniería con alta demanda de intercambio mutuo en sistemas.",
        fecha_creacion: "2026-09-29T09:15:00Z"
    }
];

const MOCK_TRUEQUES = [
    {
        id: 101,
        match_id: 1,
        usuario_propone_id: "2",
        usuario_propone_nombre: "Andrés Herrera",
        usuario_recibe_id: "1",
        usuario_recibe_nombre: "Sofía Ramírez",
        libro_propone: "Cálculo: Trascendentes Tempranas",
        libro_recibe: "Harrison: Principios de Medicina Interna",
        estado: "propuesto", // Chat BLOQUEADO hasta confirmarse
        fecha_propuesta: "2026-09-28T16:00:00Z",
        fecha_confirmacion: null,
        fecha_completado: null,
        lugar_entrega: "Punto de encuentro céntrico"
    },
    {
        id: 102,
        match_id: 2,
        usuario_propone_id: "1",
        usuario_propone_nombre: "Sofía Ramírez",
        usuario_recibe_id: "3",
        usuario_recibe_nombre: "Camila Torres",
        libro_propone: "Neuropsicología Humana",
        libro_recibe: "Principios de Microeconomía Mankiw",
        estado: "confirmado", // Chat EN CURSO / HABILITADO
        fecha_propuesta: "2026-09-26T10:00:00Z",
        fecha_confirmacion: "2026-09-27T08:30:00Z",
        fecha_completado: null,
        lugar_entrega: "Cafetería central (12:30 PM)"
    },
    {
        id: 103,
        match_id: null,
        usuario_propone_id: "1",
        usuario_propone_nombre: "Sofía Ramírez",
        usuario_recibe_id: "2",
        usuario_recibe_nombre: "Andrés Herrera",
        libro_propone: "Bioquímica Médica",
        libro_recibe: "Física Universitaria Sears",
        estado: "completado",
        fecha_propuesta: "2026-09-15T11:00:00Z",
        fecha_confirmacion: "2026-09-16T09:00:00Z",
        fecha_completado: "2026-09-18T15:20:00Z",
        lugar_entrega: "Punto de encuentro acordado",
        calificacion: {
            estrellas: 5,
            resena: "¡Excelente intercambio! El libro estaba impecable y llegó puntual.",
            fecha: "2026-09-19"
        }
    }
];

const MOCK_MENSAJES = {
    101: [], // Bloqueado, sin mensajes aún
    102: [
        {
            id: 1,
            remitente_id: "1",
            remitente_nombre: "Sofía Ramírez",
            contenido: "¡Hola Camila! Qué bueno que confirmamos el trueque. ¿Nos vemos mañana en la cafetería?",
            fecha_envio: "2026-09-27T08:35:00Z"
        },
        {
            id: 2,
            remitente_id: "3",
            remitente_nombre: "Camila Torres",
            contenido: "Perfecto Sofía, nos vemos a las 12:30. Llevo el libro en perfecto estado.",
            fecha_envio: "2026-09-27T09:00:00Z"
        },
        {
            id: 3,
            remitente_id: "1",
            remitente_nombre: "Sofía Ramírez",
            contenido: "Excelente, ya empaqué el de Neuropsicología con forro protector.",
            fecha_envio: "2026-09-27T09:10:00Z"
        }
    ],
    103: [
        {
            id: 1,
            remitente_id: "1",
            remitente_nombre: "Sofía Ramírez",
            contenido: "Ya estoy en la entrada con el libro.",
            fecha_envio: "2026-09-18T15:15:00Z"
        },
        {
            id: 2,
            remitente_id: "2",
            remitente_nombre: "Andrés Herrera",
            contenido: "¡Listo! Salgo hacia allá en dos minutos.",
            fecha_envio: "2026-09-18T15:17:00Z"
        }
    ]
};

const MOCK_RESENAS = [
    {
        id: 1,
        autor: "Andrés Herrera",
        carrera: "Ing. de Sistemas — U. Nacional",
        estrellas: 5,
        fecha: "19 Septiembre 2026",
        comentario: "Excelente experiencia de intercambio. El libro estaba exactamente como se describió. Muy puntual y amable."
    },
    {
        id: 2,
        autor: "Valeria Muñoz",
        carrera: "Psicología — U. de Medellín",
        estrellas: 5,
        fecha: "10 Septiembre 2026",
        comentario: "Intercambiamos textos académicos sin problema. Comunicación impecable y súper organizada. 100% recomendada."
    },
    {
        id: 3,
        autor: "Felipe Arango",
        carrera: "Derecho — UPB",
        estrellas: 4,
        fecha: "28 Agosto 2026",
        comentario: "El ejemplar estaba en muy buen estado general. Intercambio justo y transparente, lo haría de nuevo."
    }
];
