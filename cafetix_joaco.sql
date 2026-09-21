-- phpMyAdmin SQL Dump
-- version 5.2.1
--
-- Servidor: 127.0.0.1
-- Esquema preparado para CAFETIX JOACO (BD-2)
-- Compatible con MySQL/MariaDB (XAMPP) e InnoDB utf8mb4
--

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

SET NAMES utf8mb4;

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
-- Estructura de tabla para la tabla `tbl_pedidos`
--

CREATE TABLE `tbl_pedidos` (
  `Ped_Id_Pedido` int(11) NOT NULL,
  `Ped_Id_Usuario` int(11) DEFAULT NULL,
  `Ped_Id_Turno` int(11) DEFAULT NULL,
  `Ped_Fecha_Pedido` date DEFAULT NULL,
  `Ped_Estado_Pedido` varchar(30) DEFAULT NULL,
  `Ped_Total_Pedido` decimal(10,2) DEFAULT NULL
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
  `Usu_Estado` varchar(20) DEFAULT NULL
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

-- --------------------------------------------------------
--
-- Índices
--

ALTER TABLE `tbl_categorias`
  ADD PRIMARY KEY (`Cat_Id_Categoria`),
  ADD UNIQUE KEY `Cat_Codigo` (`Cat_Codigo`);

ALTER TABLE `tbl_detallepedido`
  ADD PRIMARY KEY (`Det_Id_Detalle_Pedido`),
  ADD KEY `Det_Id_Pedido` (`Det_Id_Pedido`),
  ADD KEY `Det_Id_Producto` (`Det_Id_Producto`);

ALTER TABLE `tbl_pedidos`
  ADD PRIMARY KEY (`Ped_Id_Pedido`),
  ADD KEY `Ped_Id_Usuario` (`Ped_Id_Usuario`),
  ADD KEY `Ped_Id_Turno` (`Ped_Id_Turno`);

ALTER TABLE `tbl_productos`
  ADD PRIMARY KEY (`Prod_Id_Producto`),
  ADD UNIQUE KEY `Prod_cod_producto` (`Prod_cod_producto`),
  ADD KEY `Prod_Id_Categoria` (`Prod_Id_Categoria`);

ALTER TABLE `tbl_roles`
  ADD PRIMARY KEY (`Rol_Id_Rol`);

ALTER TABLE `tbl_turnos`
  ADD PRIMARY KEY (`Tur_Id_Turno`),
  ADD KEY `Tur_Id_Usuario` (`Tur_Id_Usuario`);

ALTER TABLE `tbl_usuarios`
  ADD PRIMARY KEY (`Usu_Id_Usuario`),
  ADD UNIQUE KEY `Usu_Usuario` (`Usu_Usuario`),
  ADD KEY `Usu_Id_Rol` (`Usu_Id_Rol`);

ALTER TABLE `tbl_ventas`
  ADD PRIMARY KEY (`Ven_Id_Venta`),
  ADD KEY `Ven_Id_Pedido` (`Ven_Id_Pedido`),
  ADD KEY `Ven_Id_Usuario` (`Ven_Id_Usuario`);

-- --------------------------------------------------------
--
-- AUTO_INCREMENT
--

ALTER TABLE `tbl_categorias`
  MODIFY `Cat_Id_Categoria` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_detallepedido`
  MODIFY `Det_Id_Detalle_Pedido` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_pedidos`
  MODIFY `Ped_Id_Pedido` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_productos`
  MODIFY `Prod_Id_Producto` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_roles`
  MODIFY `Rol_Id_Rol` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_turnos`
  MODIFY `Tur_Id_Turno` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_usuarios`
  MODIFY `Usu_Id_Usuario` int(11) NOT NULL AUTO_INCREMENT;

ALTER TABLE `tbl_ventas`
  MODIFY `Ven_Id_Venta` int(11) NOT NULL AUTO_INCREMENT;

-- =====================================================
-- DATOS INICIALES CAFETIX JOACO
-- =====================================================

--
-- Categorías
--

INSERT INTO `tbl_categorias`
(`Cat_Id_Categoria`, `Cat_Codigo`, `Cat_Nombre_Categoria`, `Cat_Estado`) VALUES
(1, 'bebidas', 'Bebidas', 'Activo'),
(2, 'comidas', 'Comidas', 'Activo'),
(3, 'desayunos', 'Desayunos', 'Activo'),
(4, 'almuerzos', 'Almuerzos', 'Activo'),
(5, 'mecato', 'Mecato', 'Activo');

--
-- Productos
--

INSERT INTO `tbl_productos`
(`Prod_Id_Producto`, `Prod_cod_producto`, `Prod_Id_Categoria`,
 `Prod_Nombre_Producto`, `Prod_Precio`, `Prod_Disponible`,
 `Prod_Cant_est`, `Prod_Valor_Tot`, `Prod_Imagen`, `Prod_Destacado`) VALUES

(1, 'PROD001', 1, 'Gaseosa negra', 3000.00, 'Disponible', 18, 54000.00, 'gaseosa-negra.svg', 1),
(2, 'PROD002', 2, 'Empanada', 2000.00, 'Disponible', 15, 30000.00, 'empanada.svg', 1),
(3, 'PROD003', 5, 'Dedo de bocadillo', 1500.00, 'Disponible', 10, 15000.00, 'bocadillo.svg', 1),
(4, 'PROD004', 1, 'Jugo natural', 2500.00, 'Disponible', 10, 25000.00, 'jugo.svg', 0),
(5, 'PROD005', 1, 'Gaseosa', 3000.00, 'Disponible', 18, 54000.00, 'gaseosa.svg', 0),
(6, 'PROD006', 1, 'Café con leche', 2000.00, 'Disponible', 20, 40000.00, 'cafe.svg', 0),
(7, 'PROD007', 2, 'Arepa con queso', 3500.00, 'Disponible', 12, 42000.00, 'arepa.svg', 0),
(8, 'PROD008', 2, 'Perro caliente', 4500.00, 'Disponible', 6, 27000.00, 'perro.svg', 0),
(9, 'PROD009', 3, 'Desayuno completo', 6500.00, 'Disponible', 4, 26000.00, 'desayuno.svg', 0),
(10, 'PROD010', 4, 'Almuerzo del día', 8000.00, 'Agotado', 0, 0.00, 'almuerzo.svg', 0),
(11, 'PROD011', 5, 'Pan con chocolate', 1500.00, 'Disponible', 8, 12000.00, 'pan.svg', 0),
(12, 'PROD012', 5, 'Galletas', 1500.00, 'Agotado', 0, 0.00, 'galletas.svg', 0);

--
-- Roles
--

INSERT INTO `tbl_roles`
(`Rol_Id_Rol`, `Rol_Nombre_Rol`) VALUES
(1, 'cliente'),
(2, 'vendedor'),
(3, 'administrador'),
(4, 'superadmin');

--
-- Continuar AUTO_INCREMENT después de los IDs iniciales
--

ALTER TABLE `tbl_categorias` AUTO_INCREMENT = 6;
ALTER TABLE `tbl_productos` AUTO_INCREMENT = 13;
ALTER TABLE `tbl_roles` AUTO_INCREMENT = 5;

-- =====================================================
-- RELACIONES ENTRE TABLAS
-- =====================================================

ALTER TABLE `tbl_detallepedido`
  ADD CONSTRAINT `tbl_detallepedido_ibfk_1`
  FOREIGN KEY (`Det_Id_Pedido`)
  REFERENCES `tbl_pedidos` (`Ped_Id_Pedido`),

  ADD CONSTRAINT `tbl_detallepedido_ibfk_2`
  FOREIGN KEY (`Det_Id_Producto`)
  REFERENCES `tbl_productos` (`Prod_Id_Producto`);

ALTER TABLE `tbl_pedidos`
  ADD CONSTRAINT `tbl_pedidos_ibfk_1`
  FOREIGN KEY (`Ped_Id_Usuario`)
  REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`),

  ADD CONSTRAINT `tbl_pedidos_ibfk_2`
  FOREIGN KEY (`Ped_Id_Turno`)
  REFERENCES `tbl_turnos` (`Tur_Id_Turno`);

ALTER TABLE `tbl_productos`
  ADD CONSTRAINT `tbl_productos_ibfk_1`
  FOREIGN KEY (`Prod_Id_Categoria`)
  REFERENCES `tbl_categorias` (`Cat_Id_Categoria`);

ALTER TABLE `tbl_turnos`
  ADD CONSTRAINT `tbl_turnos_ibfk_1`
  FOREIGN KEY (`Tur_Id_Usuario`)
  REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`);

ALTER TABLE `tbl_usuarios`
  ADD CONSTRAINT `tbl_usuarios_ibfk_1`
  FOREIGN KEY (`Usu_Id_Rol`)
  REFERENCES `tbl_roles` (`Rol_Id_Rol`);

ALTER TABLE `tbl_ventas`
  ADD CONSTRAINT `tbl_ventas_ibfk_1`
  FOREIGN KEY (`Ven_Id_Pedido`)
  REFERENCES `tbl_pedidos` (`Ped_Id_Pedido`),

  ADD CONSTRAINT `tbl_ventas_ibfk_2`
  FOREIGN KEY (`Ven_Id_Usuario`)
  REFERENCES `tbl_usuarios` (`Usu_Id_Usuario`);

COMMIT;

-- BD-3: actualizaci�n de base de datos
