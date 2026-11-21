"""Menus of businesses onboarded from their own published material.

Bizza: transcribed from the restaurant's QR menu (MENUBIZZA_QR2026.pdf). Names, descriptions and
numbers are as printed there. The PDF states "los precios están expresados en tasa Euro BCV" and
"no incluyen 10% de servicio"; the figures are stored unchanged in `price` (the field the rest of
the app treats as USD), so the currency basis is a pending decision, see BIZZA_NOTES.

Tuple: (name, price, category, description)
"""

# https://www.pizzeriaabruzzos.com/ — 2026-11-21, public catalog endpoints
# (products, product_categories, product_extras, promotions, locations, location_hours,
# delivery_zones). Prices in USD; descriptions preserved in full.
ABRUZZOS_MENU: list[tuple[str, float, str, str]] = [
    ("Margherita", 6.5, "Pizzas", "Salsa de tomate, mozzarella fresca, albahaca"),
    ("Pepperoni", 9, "Pizzas", "Pepperoni premium, mozzarella, salsa de tomate"),
    ("Jamón", 8, "Pizzas", "Tomate, mozarella y jamon de pierna. Tamaño: Única."),
    ("Napolitana", 11, "Pizzas", "Salsa pomodoro, mozzarella de búfala, albahaca y aceite de oliva"),
    ("Bastoncini", 9.5, "Pizzas", "Bastoncitos de masa con mozzarella gratinada, acompañados de salsa pomodoro y mantequilla de ajo"),
    ("Green Gold", 1.5, "Salsas Especiales", "Albahaca salvaje y parmesano. Golpe de frescura"),
    ("Umami", 1.5, "Salsas Especiales", "El quinto sabor: adicción líquida a base de tocineta ahumada"),
    ("Aglio Rostizado", 1.5, "Salsas Especiales", "Vicio de la casa. Ajos confitados en oliva a fuego lento"),
    ("Butter Gang", 1.5, "Salsas Especiales", "Mantequilla de ajo. La más pedida por lejos"),
    ("Peperonata", 1.5, "Salsas Especiales", "Pimentón rojo ahumado vibrando a fuego alto"),
    ("Sacrilegio", 1.5, "Salsas Especiales", "Pecado favorito de la casa. Piña rostizada"),
    ("Pomodoro Segreto", 1.5, "Salsas Especiales", "Salsa madre de la pizza Margherita. La ricetta della nonna"),
    ("Magnifique", 1.5, "Salsas Especiales", "De locos. El lado oscuro y delicioso del champignon"),
    ("Hot Honey", 1.5, "Salsas Especiales", "Miel de abejas infusionada con peperoncino artesanal"),
    ("Pizza de Nutella", 7, "Postres", "Pizza dulce con Nutella"),
    ("Refresco Pepsi Cola 1LT", 2, "Bebidas", ""),
    ("Agua Minalba 355ml", 1.5, "Bebidas", ""),
    ("Refresco 7up Lata", 2.5, "Bebidas", ""),
    ("Cebolla", 8, "Pizzas", "Pizza con cebolla caramelizada sobre base de tomate y mozzarella"),
    ("Aceitunas", 8, "Pizzas", "Pizza con aceitunas negras, tomate y mozzarella"),
    ("Maiz", 8, "Pizzas", "Margherita con maiz"),
    ("Salchicha Italiana", 8, "Premium", "Pizza Margherita con salchicha italiana, albahaca y aceite de oliva "),
    ("Galleta  FUDGY", 2, "Postres", "Galleta con chispas de chocolate"),
    ("Refresco Golden Kolita 1LT", 2, "Bebidas", ""),
    ("Refresco 7up 1LT", 2, "Bebidas", ""),
    ("Refresco Golden Manzanita 1LT", 2, "Bebidas", ""),
    ("Refresco Pepsi Cola Zero 1LT", 2, "Bebidas", ""),
    ("Refresco Golden Piña 1LT", 2, "Bebidas", ""),
    ("Refresco Golden Kolita 1.5LT", 3, "Bebidas", ""),
    ("Refresco 7up 1.5LT", 3, "Bebidas", ""),
    ("Refresco Golden Manzanita 1.5LT", 3, "Bebidas", ""),
    ("Refresco Golden Kolita 2LT", 4, "Bebidas", ""),
    ("Refresco 7up 2LT", 4, "Bebidas", ""),
    ("Refresco Golden Manzanita 2LT", 4, "Bebidas", ""),
    ("Refresco Pepsi Cola Zero 2LT", 4, "Bebidas", ""),
    ("Lipton Durazno", 3, "Bebidas", ""),
    ("Lipton Limón", 3, "Bebidas", ""),
    ("Agua Sparkling Original", 3.5, "Bebidas", ""),
    ("Agua Sparkling Toronja", 3.5, "Bebidas", ""),
    ("Agua Sparkling Limón", 3.5, "Bebidas", ""),
    ("Refresco Pepsi Cola 1.5LT", 3, "Bebidas", ""),
    ("Refresco Pepsi Cola 2LT", 4, "Bebidas", ""),
    ("Refresco Pepsi Cola Lata", 2.5, "Bebidas", ""),
    ("Refresco Pepsi Zero Lata", 2.5, "Bebidas", ""),
    ("Extra: Aceitunas Negras", 1.5, "Extras", "Adicional para pizzas."),
    ("Extra: Anchoas", 3.5, "Extras", "Adicional para pizzas."),
    ("Extra: Bocconcini", 2.5, "Extras", "Adicional para pizzas."),
    ("Extra: Borde de Queso Mozzarella", 3.5, "Extras", "Adicional para pizzas."),
    ("Extra: Burrata", 4.5, "Extras", "Adicional para pizzas."),
    ("Extra: Cebolla", 1.5, "Extras", "Adicional para pizzas."),
    ("Extra: Cebolla Caramelizada", 2.5, "Extras", "Adicional para pizzas."),
    ("Extra: Champiñones", 2.5, "Extras", "Adicional para pizzas."),
    ("Extra: Galleta Caledonia", 0, "Extras", "Adicional para pizzas."),
    ("Extra: Jamón", 1.5, "Extras", "Adicional para pizzas."),
    ("Extra: Maíz", 1.5, "Extras", "Adicional para pizzas."),
    ("Extra: Mantequilla de Ajo", 1.5, "Extras", "Adicional para pizzas."),
    ("Extra: Pecorino", 2.5, "Extras", "Adicional para pizzas."),
    ("Extra: Pepperoni", 2.5, "Extras", "Adicional para pizzas."),
    ("Extra: Prosciutto", 4.5, "Extras", "Adicional para pizzas."),
    ("Extra: Queso Mozzarella", 3.5, "Extras", "Adicional para pizzas."),
    ("Extra: Rúgula", 2.5, "Extras", "Adicional para pizzas."),
    ("Extra: Tocineta", 4.5, "Extras", "Adicional para pizzas."),
    ("Promo FUDGY", 5, "Combos", "3 Galletas FUDGY (galletas con chispas de chocolate). Sin mezcla ni recargos configurados."),
    ("PROMO SKIPY", 6.5, "Combos", "Elige 2 entre Bastoncini, Pizza de Nutella, Jamón, Pepperoni, Margherita, Napolitana, Maiz, Cebolla, Aceitunas y Nestea. Permite mezclar; sin recargos configurados."),
    ("PROMO LOCA", 10, "Combos", 'Texto publicado: "2 pizzas DIFERENTES de 33 cmde cualquiera de nuestro sabores!". '
     "Elige 2 entre Margherita, Jamón, Pepperoni, Bastoncini, Napolitana, Pizza de Nutella, Cebolla, Aceitunas, Maiz y Salchicha Italiana. "
     "La configuración permite mezclar y contempla recargos por duplicados: 2 Pepperoni +$2.50; 2 Bastoncini +$2.50; "
     "2 Napolitana +$2.50; 2 Pizza de Nutella +$4. Sin extras incluidos configurados. "
     "El texto dice DIFERENTES pero la configuración contempla duplicados: confirmar esa condición con el local."),
]

ABRUZZOS_INFO = (
    "Sucursales y horarios publicados (hora local):\n"
    "Charallave, C.C. Vanessa Mall: 64MR+WJP Charallave, Miranda. Diario 09:00–22:00.\n"
    "Guatire, C.C. La Parada: 772MFC8J+58, Guatire, Miranda. Diario 11:00–22:00.\n"
    "Guatire, C.C. Buenaventura: Nivel Feria, CC Buena aventura, Guatire, Venezuela. "
    "Lun–sáb 12:00–22:00; el registro publicado del domingo dice 00:00–22:00 (confirmar con el local).\n"
    "Hatillo: C5GF+3P Caracas, Distrito Capital. Diario 09:00–22:00.\n"
    "Lechería: Av. Principal de Lechería, Anzoátegui. Diario 12:00–23:00. WhatsApp +584129467782.\n"
    "Los Palos Grandes: Primera avenida con primera transversal de Los Palos Grandes, Caracas. "
    "Diario 12:00–23:00. WhatsApp +584242735916.\n"
    "Paseo Colón: Paseo Colón, Nivel PB, Local 8, Puerto La Cruz. Diario 12:00–22:15.\n"
    "Sabana Grande: Bulevar de Sabana Grande, Local 201, Caracas. Diario 11:00–22:00. WhatsApp +584120899922.\n"
    "Santa Fe: Avenida Jose Maria Vargas, Edificio Artico, local 4, Caracas 1080, Distrito Capital. "
    "Diario 11:00–23:00. WhatsApp +584162089569.\n"
    "UCAB: Feria de Comida, Universidad Católica Andrés Bello, Caracas. Lun–vie 11:00–17:00; sáb–dom cerrado.\n"
    "Delivery: valores configurados por sucursal en la web, en USD, NO tarifas finales por zona:\n"
    "Lechería: $2. Zonas publicadas: Lechería, El Morro, Puerto La Cruz, Guaraguao, Pozuelos, Las Garzas, "
    "Barcelona Centro, El Viñedo, Boyacá, Pueblo Nuevo.\n"
    "Paseo Colón: $2. Zonas publicadas: Puerto La Cruz Centro, Paseo Colón, Pozuelos, Guaraguao, Lechería, "
    "El Morro, Las Garzas, Barcelona Centro, El Viñedo, Pueblo Nuevo.\n"
    "Santa Fe: $3. Zonas publicadas: Santa Fe, El Cafetal, Las Mercedes, Chuao, Los Naranjos, La Trinidad, "
    "Cumbres de Curumo, La Boyera, El Hatillo, Macaracuay, La California, Caurimare, Baruta, Los Samanes.\n"
    "Para las otras sucursales no hay tarifa de delivery publicada. "
    "El costo final lo calcula la tienda desde la dirección al finalizar la compra en "
    "https://www.pizzeriaabruzzos.com/ecommerce/envio. No prometer un costo fijo por zona ni delivery gratis; "
    "confirmar el costo final con la tienda antes de confirmar el total con delivery."
)

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
