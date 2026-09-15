-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Servidor: 127.0.0.1
-- Tiempo de generación: 09-09-2026 a las 00:24:44
-- Versión del servidor: 10.4.32-MariaDB
-- Versión de PHP: 8.0.30

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
  `Det_Precio_Unitario` double DEFAULT NULL,
  `Det_Subtotal` double DEFAULT NULL
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
  `Ped_Total_Pedido` double DEFAULT NULL
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
  `Prod_Precio` double DEFAULT NULL,
  `Prod_Disponible` varchar(20) DEFAULT NULL,
  `Prod_Cant_est` int(11) DEFAULT NULL,
  `Prod_Valor_Tot` double DEFAULT NULL
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
  `Usu_Contrasena` varchar(100) NOT NULL,
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
  `Ven_Total_Venta` double DEFAULT NULL,
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
  ADD PRIMARY KEY (`Cat_Id_Categoria`);

--
-- Indices de la tabla `tbl_detallepedido`
--
ALTER TABLE `tbl_detallepedido`
  ADD PRIMARY KEY (`Det_Id_Detalle_Pedido`),
  ADD KEY `Det_Id_Pedido` (`Det_Id_Pedido`),
  ADD KEY `Det_Id_Producto` (`Det_Id_Producto`);

--
-- Indices de la tabla `tbl_pedidos`
--
ALTER TABLE `tbl_pedidos`
  ADD PRIMARY KEY (`Ped_Id_Pedido`),
  ADD KEY `Ped_Id_Usuario` (`Ped_Id_Usuario`),
  ADD KEY `Ped_Id_Turno` (`Ped_Id_Turno`);

--
-- Indices de la tabla `tbl_productos`
--
ALTER TABLE `tbl_productos`
  ADD PRIMARY KEY (`Prod_Id_Producto`),
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
  ADD KEY `Tur_Id_Usuario` (`Tur_Id_Usuario`);

--
-- Indices de la tabla `tbl_usuarios`
--
ALTER TABLE `tbl_usuarios`
  ADD PRIMARY KEY (`Usu_Id_Usuario`),
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
-- AUTO_INCREMENT de la tabla `tbl_pedidos`
--
ALTER TABLE `tbl_pedidos`
  MODIFY `Ped_Id_Pedido` int(11) NOT NULL AUTO_INCREMENT;

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
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
