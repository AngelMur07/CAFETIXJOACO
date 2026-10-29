-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Esquema preparado para CAFETIX JOACO (BD-2)
-- Compatible con MySQL/MariaDB (XAMPP) e InnoDB utf8mb4
--

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de datos: `cafetix_joaco`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_categorias`
--

CREATE TABLE `tbl_categorias` (
  `Cat_Id_Categoria` int(11) NOT NULL,
  `Cat_Codigo` varchar(50) NOT NULL,
  `Cat_Nombre_Categoria` varchar(70) NOT NULL,
  `Cat_Estado` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_detallepedido`
--

CREATE TABLE `tbl_detallepedido` (
  `Det_Id_Detalle_Pedido` int(11) NOT NULL,
  `Det_Id_Pedido` int(11) DEFAULT NULL,
  `Det_Id_Producto` int(11) DEFAULT NULL,
  `Det_Cantidad` int(11) DEFAULT NULL,
  `Det_Precio_Unitario` decimal(10,2) DEFAULT NULL,
  `Det_Subtotal` decimal(10,2) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_encuestas`
--

CREATE TABLE `tbl_encuestas` (
  `Enc_Id_Encuesta` int(11) NOT NULL,
  `Enc_Id_Usuario` int(11) DEFAULT NULL,
  `Enc_Experiencia` tinyint(4) DEFAULT NULL,
  `Enc_Facilidad` tinyint(4) DEFAULT NULL,
  `Enc_Comentario` text DEFAULT NULL,
  `Enc_Fecha` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_pedidos`
--

CREATE TABLE `tbl_pedidos` (
  `Ped_Id_Pedido` int(11) NOT NULL,
  `Ped_Id_Usuario` int(11) DEFAULT NULL,
  `Ped_Id_Turno` int(11) DEFAULT NULL,
  `Ped_Fecha_Pedido` date DEFAULT NULL,
  `Ped_Estado_Pedido` varchar(30) DEFAULT NULL,
  `Ped_Total_Pedido` decimal(10,2) DEFAULT NULL,
  `Ped_Token_Compra` varchar(128) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_pqr`
--

CREATE TABLE `tbl_pqr` (
  `Pqr_Id_Pqr` int(11) NOT NULL,
  `Pqr_Id_Usuario` int(11) DEFAULT NULL,
  `Pqr_Tipo` varchar(30) NOT NULL,
  `Pqr_Asunto` varchar(100) DEFAULT NULL,
  `Pqr_Mensaje` text NOT NULL,
  `Pqr_Fecha` datetime NOT NULL,
  `Pqr_Estado` varchar(30) NOT NULL DEFAULT 'Pendiente'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_productos`
--

CREATE TABLE `tbl_productos` (
  `Prod_Id_Producto` int(11) NOT NULL,
  `Prod_cod_producto` varchar(50) NOT NULL,
  `Prod_Id_Categoria` int(11) DEFAULT NULL,
  `Prod_Nombre_Producto` varchar(100) NOT NULL,
  `Prod_Precio` decimal(10,2) DEFAULT NULL,
  `Prod_Disponible` varchar(20) DEFAULT NULL,
  `Prod_Cant_est` int(11) DEFAULT NULL,
  `Prod_Valor_Tot` decimal(10,2) DEFAULT NULL,
  `Prod_Imagen` varchar(255) DEFAULT NULL,
  `Prod_Destacado` tinyint(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_roles`
--

CREATE TABLE `tbl_roles` (
  `Rol_Id_Rol` int(11) NOT NULL,
  `Rol_Nombre_Rol` varchar(70) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_turnos`
--

CREATE TABLE `tbl_turnos` (
  `Tur_Id_Turno` int(11) NOT NULL,
  `Tur_Id_Usuario` int(11) DEFAULT NULL,
  `Tur_Numero_Turno` int(11) DEFAULT NULL,
  `Tur_Fecha` date DEFAULT NULL,
  `Tur_Hora_Solicitud` time DEFAULT NULL,
  `Tur_Estado_Turno` varchar(30) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_usuarios`
--

CREATE TABLE `tbl_usuarios` (
  `Usu_Id_Usuario` int(11) NOT NULL,
  `Usu_Id_Rol` int(11) DEFAULT NULL,
  `Usu_Nombre` varchar(70) NOT NULL,
  `Usu_Apellido` varchar(70) NOT NULL,
  `Usu_Usuario` varchar(70) NOT NULL,
  `Usu_Contrasena` varchar(255) NOT NULL,
  `Usu_Estado` varchar(20) DEFAULT NULL,
  `Usu_Documento` varchar(30) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `tbl_ventas`
--

CREATE TABLE `tbl_ventas` (
  `Ven_Id_Venta` int(11) NOT NULL,
  `Ven_Id_Pedido` int(11) DEFAULT NULL,
  `Ven_Fecha_Venta` date DEFAULT NULL,
  `Ven_Total_Venta` decimal(10,2) DEFAULT NULL,
  `Ven_Metodo_Pago` varchar(50) DEFAULT NULL,
  `Ven_Estado_Pago` varchar(30) DEFAULT NULL,
  `Ven_Id_Usuario` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `tbl_categorias`
--
ALTER TABLE `tbl_categorias`
  ADD PRIMARY KEY (`Cat_Id_Categoria`),
  ADD UNIQUE KEY `Cat_Codigo` (`Cat_Codigo`);

--
-- Indices de la tabla `tbl_detallepedido`
--
ALTER TABLE `tbl_detallepedido`
  ADD PRIMARY KEY (`Det_Id_Detalle_Pedido`),
  ADD KEY `Det_Id_Pedido` (`Det_Id_Pedido`),
  ADD KEY `Det_Id_Producto` (`Det_Id_Producto`);

--
-- Indices de la tabla `tbl_encuestas`
--
ALTER TABLE `tbl_encuestas`
  ADD PRIMARY KEY (`Enc_Id_Encuesta`),
  ADD UNIQUE KEY `Enc_Id_Usuario` (`Enc_Id_Usuario`);

--
-- Indices de la tabla `tbl_pedidos`
--
ALTER TABLE `tbl_pedidos`
  ADD PRIMARY KEY (`Ped_Id_Pedido`),
  ADD UNIQUE KEY `uq_ped_token_compra` (`Ped_Token_Compra`),
  ADD KEY `Ped_Id_Usuario` (`Ped_Id_Usuario`),
  ADD KEY `Ped_Id_Turno` (`Ped_Id_Turno`);

--
-- Indices de la tabla `tbl_pqr`
--
ALTER TABLE `tbl_pqr`
  ADD PRIMARY KEY (`Pqr_Id_Pqr`),
  ADD KEY `Pqr_Id_Usuario` (`Pqr_Id_Usuario`),
  ADD KEY `Pqr_Estado` (`Pqr_Estado`);

--
-- Indices de la tabla `tbl_productos`
--
ALTER TABLE `tbl_productos`
  ADD PRIMARY KEY (`Prod_Id_Producto`),
  ADD UNIQUE KEY `Prod_cod_producto` (`Prod_cod_producto`),
  ADD KEY `Prod_Id_Categoria` (`Prod_Id_Categoria`);

--
-- Indices de la tabla `tbl_roles`
--
ALTER TABLE `tbl_roles`
  ADD PRIMARY KEY (`Rol_Id_Rol`);

--
-- Indices de la tabla `tbl_turnos`
--
ALTER TABLE `tbl_turnos`
  ADD PRIMARY KEY (`Tur_Id_Turno`),
  ADD UNIQUE KEY `uq_tur_numero_turno` (`Tur_Numero_Turno`),
  ADD KEY `Tur_Id_Usuario` (`Tur_Id_Usuario`);

--
-- Indices de la tabla `tbl_usuarios`
--
ALTER TABLE `tbl_usuarios`
  ADD PRIMARY KEY (`Usu_Id_Usuario`),
  ADD UNIQUE KEY `Usu_Usuario` (`Usu_Usuario`),
  ADD UNIQUE KEY `Usu_Documento` (`Usu_Documento`),
  ADD KEY `Usu_Id_Rol` (`Usu_Id_Rol`);

--
-- Indices de la tabla `tbl_ventas`
--
ALTER TABLE `tbl_ventas`
  ADD PRIMARY KEY (`Ven_Id_Venta`),
  ADD KEY `Ven_Id_Pedido` (`Ven_Id_Pedido`),
  ADD KEY `Ven_Id_Usuario` (`Ven_Id_Usuario`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `tbl_categorias`
--
ALTER TABLE `tbl_categorias`
  MODIFY `Cat_Id_Categoria` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_detallepedido`
--
ALTER TABLE `tbl_detallepedido`
  MODIFY `Det_Id_Detalle_Pedido` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_encuestas`
--
ALTER TABLE `tbl_encuestas`
  MODIFY `Enc_Id_Encuesta` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_pedidos`
--
ALTER TABLE `tbl_pedidos`
  MODIFY `Ped_Id_Pedido` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_pqr`
--
ALTER TABLE `tbl_pqr`
  MODIFY `Pqr_Id_Pqr` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_productos`
--
ALTER TABLE `tbl_productos`
  MODIFY `Prod_Id_Producto` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_roles`
--
ALTER TABLE `tbl_roles`
  MODIFY `Rol_Id_Rol` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_turnos`
--
ALTER TABLE `tbl_turnos`
  MODIFY `Tur_Id_Turno` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_usuarios`
--
ALTER TABLE `tbl_usuarios`
  MODIFY `Usu_Id_Usuario` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de la tabla `tbl_ventas`
--
ALTER TABLE `tbl_ventas`
  MODIFY `Ven_Id_Venta` int(11) NOT NULL AUTO_INCREMENT;

--
-- Restricciones para tablas volcadas
--

--
-- Filtros para la tabla `tbl_detallepedido`
--
ALTER TABLE `tbl_detallepedido`
  ADD CONSTRAINT `tbl_detallepedido_ibfk_1` FOREIGN KEY (`Det_Id_Pedido`) REFERENCES `tbl_pedidos` (`Ped_Id_Pedido`),
  ADD CONSTRAINT `tbl_detallepedido_ibfk_2` FOREIGN KEY (`Det_Id_Producto`) REFERENCES `tbl_productos` (`Prod_Id_Producto`);

--
-- Filtros para la tabla `tbl_encuestas`
--
ALTER TABLE `tbl_encuestas`
  ADD CONSTRAINT `tbl_encuestas_ibfk_1` FOREIGN KEY (`Enc_Id_Usuario`) REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`) ON DELETE SET NULL;

--
-- Filtros para la tabla `tbl_pedidos`
--
ALTER TABLE `tbl_pedidos`
  ADD CONSTRAINT `tbl_pedidos_ibfk_1` FOREIGN KEY (`Ped_Id_Usuario`) REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`),
  ADD CONSTRAINT `tbl_pedidos_ibfk_2` FOREIGN KEY (`Ped_Id_Turno`) REFERENCES `tbl_turnos` (`Tur_Id_Turno`);

--
-- Filtros para la tabla `tbl_productos`
--
ALTER TABLE `tbl_productos`
  ADD CONSTRAINT `tbl_productos_ibfk_1` FOREIGN KEY (`Prod_Id_Categoria`) REFERENCES `tbl_categorias` (`Cat_Id_Categoria`);

--
-- Filtros para la tabla `tbl_pqr`
--
ALTER TABLE `tbl_pqr`
  ADD CONSTRAINT `tbl_pqr_ibfk_1` FOREIGN KEY (`Pqr_Id_Usuario`) REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`) ON DELETE SET NULL;

--
-- Filtros para la tabla `tbl_turnos`
--
ALTER TABLE `tbl_turnos`
  ADD CONSTRAINT `tbl_turnos_ibfk_1` FOREIGN KEY (`Tur_Id_Usuario`) REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`);

--
-- Filtros para la tabla `tbl_usuarios`
--
ALTER TABLE `tbl_usuarios`
  ADD CONSTRAINT `tbl_usuarios_ibfk_1` FOREIGN KEY (`Usu_Id_Rol`) REFERENCES `tbl_roles` (`Rol_Id_Rol`);

--
-- Filtros para la tabla `tbl_ventas`
--
ALTER TABLE `tbl_ventas`
  ADD CONSTRAINT `tbl_ventas_ibfk_1` FOREIGN KEY (`Ven_Id_Pedido`) REFERENCES `tbl_pedidos` (`Ped_Id_Pedido`),
  ADD CONSTRAINT `tbl_ventas_ibfk_2` FOREIGN KEY (`Ven_Id_Usuario`) REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`);

-- =====================================================
-- DATOS INICIALES CAFETIX JOACO
-- =====================================================

-- Categorías (sin "todos": es solo filtro de interfaz)
-- desayunos/almuerzos se conservan (legacy, sin productos en el seed)
INSERT INTO `tbl_categorias` (`Cat_Id_Categoria`, `Cat_Codigo`, `Cat_Nombre_Categoria`, `Cat_Estado`) VALUES
(1, 'bebidas', 'Bebidas', 'Activo'),
(2, 'comidas', 'Comidas', 'Activo'),
(3, 'desayunos', 'Desayunos', 'Activo'),
(4, 'almuerzos', 'Almuerzos', 'Activo'),
(5, 'mecato', 'Mecato', 'Activo'),
(6, 'recien-preparadas', 'Comidas recién preparadas', 'Activo');

-- Catálogo definitivo (18 Access + 2 comidas recién preparadas)
-- Prod_Imagen: archivo en img/, guardado como ../nombre.jpg. NULL si el producto no tiene foto.
INSERT INTO `tbl_productos` (`Prod_Id_Producto`, `Prod_cod_producto`, `Prod_Id_Categoria`, `Prod_Nombre_Producto`, `Prod_Precio`, `Prod_Disponible`, `Prod_Cant_est`, `Prod_Valor_Tot`, `Prod_Imagen`, `Prod_Destacado`) VALUES
(1, 'GB-20', 1, 'Coca-Cola personal', 3500.00, 'Disponible', 60, 210000.00, '../coca-cola-personal.jpg', 0),
(2, 'GB-23', 1, 'Sprite personal', 3000.00, 'Disponible', 80, 240000.00, '../sprite-personal.jpg', 0),
(3, 'GB-06', 1, 'Pony Malta', 3000.00, 'Disponible', 35, 105000.00, '../pony-malta.jpg', 0),
(4, 'GB-08', 1, 'Manzana Postobón', 3000.00, 'Disponible', 30, 90000.00, '../manzana-postobon.jpg', 0),
(5, 'GB-15', 1, 'Agua en bolsa', 300.00, 'Disponible', 200, 60000.00, '../agua-en-bolsa.jpg', 0),
(6, 'GB-10', 1, 'Jugo Hit botella', 3500.00, 'Disponible', 30, 105000.00, '../jugo-hit-botella.jpg', 0),
(7, 'GB-18', 1, 'Gatorade', 4000.00, 'Disponible', 30, 120000.00, '../gatorade.jpg', 0),
(8, 'CM-01', 2, 'Empanada de carne', 1500.00, 'Disponible', 40, 60000.00, '../empanada-de-carne.jpg', 0),
(9, 'CM-07', 2, 'Cubano', 2000.00, 'Disponible', 30, 60000.00, '../cubano.jpg', 0),
(10, 'CM-08', 2, 'Torta de carne pequeña', 2600.00, 'Disponible', 15, 39000.00, '../torta-de-carne-pequena.jpg', 0),
(11, 'CM-09', 2, 'Torta de carne grande', 3600.00, 'Disponible', 20, 72000.00, '../torta-de-carne-grande.jpg', 0),
(12, 'CM-10', 2, 'Pastel de papa', 3500.00, 'Disponible', 25, 87500.00, '../pastel-de-papa.jpg', 0),
(13, 'SN-01', 5, 'Chocolatina Jet', 1000.00, 'Disponible', 80, 80000.00, '../chocolatina-jet.jpg', 0),
(14, 'SN-02', 5, 'Chocoramo', 2500.00, 'Disponible', 50, 125000.00, '../chocoramo.jpg', 0),
(15, 'SN-03', 5, 'Galletas Festival', 2000.00, 'Disponible', 55, 110000.00, '../galletas-festival.jpg', 0),
(16, 'SN-07', 5, 'Papas Margarita', 3000.00, 'Disponible', 60, 180000.00, '../papas-margarita.jpg', 0),
(17, 'SN-08', 5, 'Detodito', 4500.00, 'Disponible', 40, 180000.00, '../detodito.jpg', 0),
(18, 'SN-09', 5, 'Papas limon', 3000.00, 'Disponible', 40, 120000.00, '../papas-limon.jpg', 0),
(19, 'PREP-DES-01', 6, 'Desayuno del día', 12000.00, 'Disponible', 30, 360000.00, '../desayuno-del-dia.jpg', 0),
(20, 'PREP-ALM-01', 6, 'Almuerzo del día', 15000.00, 'Disponible', 30, 450000.00, '../almuerzo-del-dia.jpg', 0);

-- Roles de CAFETIX JOACO
INSERT INTO `tbl_roles` (`Rol_Id_Rol`, `Rol_Nombre_Rol`) VALUES
(1, 'cliente'),
(2, 'vendedor'),
(3, 'administrador'),
(4, 'superadmin');

-- Continuar AUTO_INCREMENT después de los IDs iniciales

-- Usuarios staff para instalación limpia (hashes Werkzeug, no texto plano)
INSERT INTO `tbl_usuarios` (`Usu_Id_Usuario`, `Usu_Id_Rol`, `Usu_Nombre`, `Usu_Apellido`, `Usu_Usuario`, `Usu_Contrasena`, `Usu_Estado`, `Usu_Documento`) VALUES
(1, 2, 'Vendedor', 'Cafetix', 'Vendedor', 'scrypt:32768:8:1$UwUi3hgrPTp1Pqd4$75eec8a03cd9e1b3db91017dc4daa0382240040489e406ddc3c617ec837fda28582e35e89b5352714db8dc5acf8b78d591e90baf2bb150e4d20320b2ae77fd33', 'Activo', '1000000003'),
(2, 3, 'Administrador', 'Cafetix', 'Administrador', 'scrypt:32768:8:1$Z6gw58GO0QSeSc6k$62ab668bfdcb927e513498463908eaa44c113593c88238603cbc2d04f15a9265c0033f34a66589e22edc09b0a97a53c62df9321a02e99457c2a575d9d2d270f5', 'Activo', '1000000002'),
(3, 4, 'Superadmin', 'Cafetix', 'Superadmin', 'scrypt:32768:8:1$rk9zToRDxijIe1Zp$0e3b1c7ec3d93b86e6cd097719849b36dcfc27613ea4eaa2f9843ea381a36ee9205cacadcdc72b8305522fdf608207ea552c60c108e805d1eb3737c979ae2073', 'Activo', '1000000001');

ALTER TABLE `tbl_usuarios` AUTO_INCREMENT = 4;
ALTER TABLE `tbl_categorias` AUTO_INCREMENT = 7;
ALTER TABLE `tbl_productos` AUTO_INCREMENT = 21;
ALTER TABLE `tbl_roles` AUTO_INCREMENT = 5;

-- --------------------------------------------------------
--
-- Estructura de tabla para `tbl_config_operativa`
-- Almacena el estado operativo del sistema entre reinicios de Flask.
-- Solo debe existir una fila (conf_id = 1).
--

CREATE TABLE IF NOT EXISTS `tbl_config_operativa` (
  `conf_id`             TINYINT UNSIGNED  NOT NULL DEFAULT 1,
  `sistema_habilitado`  TINYINT(1)        NOT NULL DEFAULT 1
                          COMMENT '1 = habilitado, 0 = deshabilitado',
  `bloqueo_admin`       TINYINT(1)        NOT NULL DEFAULT 0
                          COMMENT '1 = bloqueo activo (solo Admin puede levantar)',
  `extension_hasta`     TIME              DEFAULT NULL
                          COMMENT 'Hora de cierre de la extension o apertura extraordinaria',
  `extension_jornada`   VARCHAR(50)       DEFAULT NULL
                          COMMENT 'Nombre de jornada o "extraordinaria"',
  `extension_fecha`     DATE              DEFAULT NULL
                          COMMENT 'Fecha de apertura extraordinaria; NULL para extensiones normales',
  `extension_autor`     VARCHAR(20)       DEFAULT NULL
                          COMMENT '"vendedor" o "administrador"',
  `actualizado_en`      DATETIME          NOT NULL
                          DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`conf_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
  COMMENT='Estado operativo persistente. Una sola fila (conf_id=1).';

--
-- Fila inicial: estado seguro por defecto.
-- INSERT IGNORE no falla si la fila ya existe (re-importaciones seguras).
--
INSERT IGNORE INTO `tbl_config_operativa`
  (`conf_id`, `sistema_habilitado`, `bloqueo_admin`,
   `extension_hasta`, `extension_jornada`, `extension_fecha`, `extension_autor`)
VALUES
  (1, 1, 0, NULL, NULL, NULL, NULL);

-- --------------------------------------------------------
-- PROPUESTA DE MEJORA: Columna Prod_Costo para Utilidad de Inventario
-- Permite calcular la utilidad real por producto:
-- Utilidad unitaria = Prod_Precio - Prod_Costo
-- Para habilitarla en la base de datos, ejecute:
-- ALTER TABLE `tbl_productos` ADD COLUMN `Prod_Costo` decimal(10,2) DEFAULT NULL AFTER `Prod_Precio`;
-- --------------------------------------------------------

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
