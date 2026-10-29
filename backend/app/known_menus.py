"""Menus of businesses onboarded from their own published material.

Bizza: transcribed from the restaurant's QR menu (MENUBIZZA_QR2026.pdf). Names, descriptions and
numbers are as printed there. The PDF states "los precios están expresados en tasa Euro BCV" and
"no incluyen 10% de servicio"; the figures are stored unchanged in `price` (the field the rest of
the app treats as USD), so the currency basis is a pending decision, see BIZZA_NOTES.

Tuple: (name, price, category, description)
"""

BIZZA_NOTES = [
    "Los precios del PDF están 'expresados en tasa Euro BCV' y no incluyen 10% de servicio. "
    "Se cargaron las cifras tal cual; falta decidir si son euros o dólares.",
    "Cesar: un solo precio para pollo a la plancha o camarones; la variante no tiene precio propio.",
    "Extras: el PDF da un precio por grupo (regulares / premium) y dos premium con precio propio.",
    "Refrescos de 1 L, 1,5 L y 2 L: el PDF indica 'solo delivery'.",
]

BIZZA_MENU: list[tuple[str, float, str, str]] = [
    # --- Entradas
    ("TEQUEÑOS", 9, "Entradas", "7 unidades de tequeños hecho en casa, rellenos de queso tipo llanero y acompañados de una salsa secreta."),
    ("CARPACCIO DE LOMITO", 13, "Entradas", "Finas rebanadas de lomo de res, aderezado con aceite de oliva extra virgen, sal marina, tomates confitados, rúgula y queso parmesano."),
    ("ALITAS BBQ", 10, "Entradas", "8 unidades de alitas fritas bañadas en salsas bbq de la casa."),
    ("MOZZARELLA STICKS", 9, "Entradas", "Dedos de nuestro queso mozzarella artesanal, empanizados con nuestra mezcla especial, acompañadas de salsa bizzera y pesto."),
    ("BIZZA STICKS", 8, "Entradas", "Trozos de nuestra masa de pizza fermentada por 48 horas, cubiertas en nuestro queso mozzarella artesanal y acompañado de salsa bizzera."),
    ("CHICKEN TENDERS", 12, "Entradas", "Tiras de pechuga de pollo empanizadas con nuestra mezcla especial, y acompañados con papas fritas"),
    ("LOS POLLITOS", 12, "Entradas", "12 bites de pollo crujiente bañado en 3 salsas: 4 BBQ, 4 miel infusionada en pepperoncini y 4 con mantequilla de ajo y perejil."),
    ("TARTAR DE LOMITO", 10.5, "Entradas", "Lomito picado finamente con aderezo de mostaza antigua acompañado de tostada de pan artesanal"),
    ("PAPAS LOCAS", 14.5, "Entradas", "Mix de lomito y pechuga de pollo sobre una cama de papas fritas, acompañado de nuestras salsas especiales y mezcla de quesos."),
    ("LANGOSTINOS REBOZADOS", 14, "Entradas", "Langostinos rebozados con panko, acompañados de salsa tártara hecha en casa."),
    ("AROS DE CEBOLLA", 8, "Entradas", "Aros de cebolla súper crujientes acompañados de salsa bbq de la casa."),
    # --- Panini
    ("PANINO JAMÓN SERRANO Y MERMELADA DE PIÑA", 16, "Panini", "Pan de alta hidratación, Jamón serrano, mermelada de piña artesanal, Rúgula fresca"),
    ("PANINO DE MORTADELA Y PESTO", 13, "Panini", "Pan de alta hidratación, mortadela italiana, stracciatella, pesto y tropiezos de pistacho."),
    ("PANINO CRISPY PESTO", 10, "Panini", "Pan de alta hidratación, pechuga de pollo empanizada, tomates confitados y cremosa mayopesto."),
    ("PANINO PHILLY CHEESESTEAK", 9, "Panini", "Pan de alta hidratación, Tiras de lomito, cebolla a la plancha y queso fundido"),
    # --- Ensaladas
    ("CESAR", 12, "Ensaladas", "Ensalada Cesar con pollo a la placha/camarones."),
    ("DE LA CASA", 12.5, "Ensaladas", "Ensalada de lechuga, rúgula, zanahoria en juliana tomates cherrys, aderezo de mostaza miel con queso pecorino y trozos de queso de cabra y pollo al grill."),
    # --- Pizzas
    ("MARGARITA", 10, "Pizzas", "Salsa bizzera y Mozzarella artesanal."),
    ("PEPPERONI", 12, "Pizzas", "Salsa bizzera, Mozzarella artesanal y Pepperoni."),
    ("JAMÓN", 11.5, "Pizzas", "Salsa bizzera, Mozzarella artesanal y Jamón."),
    ("SUNNY CHEESE", 19, "Pizzas", "Forma de estrella con bordes rellenos de ricotta y Pesto, Mozzarella artesanal, Salsa bizzera, Queso burrata, Tomates cherry y Rúgula."),
    ("CREME BACON", 14, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Cebolla caramelizada, Tocineta crunchy y Queso crema."),
    ("TOCINETA Y MAÍZ", 13, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Tocineta y Maíz."),
    ("CAPRESA", 14.5, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Tomates Cherry, Salsa Pesto y Boconccinis."),
    ("VEGETARIANA", 14, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Pimentón, Cebolla, Maíz, Aceitunas, champiñones."),
    ("FIT 9", 12.5, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Chorizo ahumado, Chistorra, Pimentón y Cebolla."),
    ("JIMIN SIRRINI", 18, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Jamón serrano, Rúgula, Parmesano, reducción de balsámico y Aceitunas negras."),
    ("3 QUESOS", 12.5, "Pizzas", "Salsa bizzera, Mozzarella artesanal, queso parmesano y queso azul."),
    ("PUESTA PAL PESTO", 13.5, "Pizzas", "Base de pesto de albahaca, Mozzarella artesanal, Parmesano y Pepperoni."),
    ("TAN BLANCA", 15, "Pizzas", "Base de salsa (Tipo alfredo), Mozzarella artesanal, Champiñones, Parmesano, Maíz y Tocineta crunchy."),
    ("BOSS 2", 13.5, "Pizzas", "Salsa, mozarella artesanal, Pepperoni, Jamón y tocineta."),
    ("SPICY HONEY PEPPERONI", 14, "Pizzas", "Salsa Bizzera, Mozzarella artesanal, doble pepperoni y miel infusionada con pepperoncini."),
    ("CHICKEN BBQ", 14.5, "Pizzas", "Salsa BBQ hecha en casa, queso mozzarella, pollo crispy, salsa ranch y perejil."),
    ("MORTADELA PISTACHO", 21, "Pizzas", "Base de pesto de pistacho, mortadela italiana, stracciatella, lluvia de pistacho y aceite de oliva extra virgen."),
    ("TRUFASICA", 14.5, "Pizzas", "Salsa blanca tipo Alfredo, Mozzarella artesanal, parmesano, champiñones y Aceite de trufa."),
    ("BIZZCESAR", 15, "Pizzas", "Aderezo césar, queso pecorino, pollo crispy, lechuga y tocineta crunchy."),
    ("OHANA", 14.5, "Pizzas", "Salsa bizzera, Mozzarella artesanal, Tocineta, piña confitada y Parmesano."),
    # --- Extras para pizzas
    ("EXTRAS REGULARES", 1, "Extras para pizzas", "Jamón, Tocineta, Maíz, Pimentón, Cebolla, Chorizo ahumado, Aceitunas, Extra queso."),
    ("EXTRAS PREMIUM", 2, "Extras para pizzas", "Pepperoni, Cebolla Caramelizada, Queso Azul, Queso Crema, Bordes de Queso y Tocineta, Champiñones, Anchoas, Bordes de Queso, Chistorra, Pesto, Queso Parmesano, Rúgula, Boconccinis."),
    ("EXTRA TOCINETA CRUNCHY", 3, "Extras para pizzas", "Extra premium con precio propio."),
    ("EXTRA JAMÓN SERRANO", 4, "Extras para pizzas", "Extra premium con precio propio."),
    # --- Pastas
    ("NAPOLI BOMB", 11, "Pastas", "Spaghetti napole con mozzarella frita, tocineta, parmesano, albahaca y orégano."),
    ("ALLA VODKA CON CAMARONES", 12, "Pastas", "Salsa cremosa a base de camarones, pure de tomate, vodka y crema de leche."),
    ("CRISPY CHICKEN ALFREDO", 13, "Pastas", "Linguini en salsa Alfredo coronado con suprema de pollo crispy."),
    ("MAC AND CHEESE GRATINADOS", 10, "Pastas", "Macarrones en salsa de quesos gratinados y tocineta crunchy."),
    ("RAGU", 11, "Pastas", "Linguini con Ragu de carne cocinado a fuego lento en salsa de tomate y vino tinto"),
    ("PORK & CHEESE", 14, "Pastas", "Linguini con salsa napolitana cremosa acompañada de albondigas de cerdo y queso parmesano."),
    ("PASTICHO", 12, "Pastas", "Pasta artesanal con ragu de carne, salsa bechamel, queso parmesano y mozzarella."),
    # --- Carnes y aves
    ("PARRILLA MIXTA", 13.5, "Carnes y aves", "Mix de lomito y pechuga de pollo acompañado con papas fritas."),
    ("COSTILLAS BBQ", 15, "Carnes y aves", "Costillas de cerdo en salsa BBQ acompañado con papas fritas."),
    ("POLLO A LA PARMIGIANA", 16, "Carnes y aves", "Milanesa de pechuga de pollo empanizada cubierta con salsa napolitana y queso mozarella fundido."),
    ("LOMITO SOL Y LUNA", 19, "Carnes y aves", "Medallones de lomito bañado en salsas, una base de pimienta y la otra a base de queso azul con nueces."),
    ("LOMITO AL VINO", 20, "Carnes y aves", "Medallones de lomito en reducción de vino tinto acompañado con puré de papa."),
    ("BEEF BOURGUIGNON", 11, "Carnes y aves", "Dados de res y vegetales estofados lentamente en vino en una cama de pure de papa."),
    # --- Postres
    ("BROWNIE", 9, "Postres", "con helado y caramelo salado."),
    ("COOKIE SKILLET", 9, "Postres", "Galleta rellena de nutella con helado."),
    ("BIZELLA", 9, "Postres", "Pizza de Nutella, con lluvia de oreo y bordes de pirulin."),
    ("CHEESECAKE DE FRESA", 9, "Postres", "Cremosa tarta de queso horneada con base crujiente de galletas cubierta de salsa de frutos rojos"),
    ("CHOCOTORTA", 8, "Postres", "Torta estilo argentina en capas de galleta de cacao, y crema de dulce de leche."),
    # --- Bebidas
    ("BIRRAS NACIONALES", 2, "Bebidas", ""),
    ("AGUA 300ml", 1, "Bebidas", ""),
    ("AGUA 600ml", 1.5, "Bebidas", ""),
    ("REFRESCOS DE LATA", 2, "Bebidas", ""),
    ("REFRESCO DE BOMBONITA", 2, "Bebidas", ""),
    ("NESTEA", 2, "Bebidas", ""),
    ("REFRESCO 1L.", 2.5, "Bebidas", "Solo delivery."),
    ("REFRESCO 1.5L.", 3, "Bebidas", "Solo delivery."),
    ("REFRESCO 2L.", 3.5, "Bebidas", "Solo delivery."),
    ("JUGO NATURAL DE FRESA", 3.75, "Bebidas", "Jugos naturales."),
    ("JUGO NATURAL DE PIÑA", 3.5, "Bebidas", "Jugos naturales."),
    ("JUGO NATURAL DE MELOCOTÓN", 3.5, "Bebidas", "Jugos naturales."),
    ("JUGO NATURAL DE MORA", 3.75, "Bebidas", "Jugos naturales."),
    ("JUGO NATURAL DE FRESA MORA", 4.5, "Bebidas", "Jugos naturales."),
    ("JUGO NATURAL DE FRESA PARCHITA", 4, "Bebidas", "Jugos naturales."),
]
