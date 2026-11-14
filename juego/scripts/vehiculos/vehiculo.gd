extends CharacterBody3D
## Vehículo provisional de BARA-DRIVE.
## Controles: W acelera, S frena y luego marcha atrás, A/D giran, C cambia de cámara.

const VELOCIDAD_MAX_DELANTE := 36.0  # m/s (~129 km/h)
const VELOCIDAD_MAX_ATRAS := 8.0  # m/s (~29 km/h)
const ACELERACION := 9.0  # m/s^2
const FUERZA_FRENO := 18.0  # m/s^2
const RESISTENCIA := 2.5  # m/s^2 de arrastre sin input
const GIRO_MAX := 1.4  # rad/s a baja velocidad
const GIRO_MIN := 0.4  # rad/s a velocidad máxima
const GRAVEDAD := 20.0  # m/s^2

var velocidad_lineal := 0.0  # firma: + adelante, − atrás (m/s)
var velocidad_vertical := 0.0
var camara_exterior_activa := false
var _c_anterior := false

@onready var camara_interior: Camera3D = $CamaraInterior
@onready var camara_exterior: Camera3D = $CamaraExterior


func _physics_process(delta: float) -> void:
	var acelerar := Input.is_key_pressed(KEY_W)
	var frenar := Input.is_key_pressed(KEY_S)
	var izquierda := Input.is_key_pressed(KEY_A)
	var derecha := Input.is_key_pressed(KEY_D)

	var c_actual := Input.is_key_pressed(KEY_C)
	if c_actual and not _c_anterior:
		alternar_camara()
	_c_anterior = c_actual

	if is_on_floor():
		velocidad_vertical = 0.0
		_aplicar_traccion(delta, acelerar, frenar)
		_aplicar_direccion(delta, izquierda, derecha)
	else:
		velocidad_vertical -= GRAVEDAD * delta

	var adelante := -global_transform.basis.z
	velocity = adelante * velocidad_lineal + Vector3.UP * velocidad_vertical
	move_and_slide()


func _aplicar_traccion(delta: float, acelerar: bool, frenar: bool) -> void:
	if frenar:
		# Frena en marcha adelante; detenido, entra en marcha atrás.
		if velocidad_lineal > 0.05:
			velocidad_lineal = maxf(velocidad_lineal - FUERZA_FRENO * delta, 0.0)
		else:
			velocidad_lineal = maxf(velocidad_lineal - ACELERACION * delta, -VELOCIDAD_MAX_ATRAS)
	elif acelerar:
		# Acelera adelante; en marcha atrás, frena hasta detenerse.
		if velocidad_lineal < -0.05:
			velocidad_lineal = minf(velocidad_lineal + FUERZA_FRENO * delta, 0.0)
		else:
			velocidad_lineal = minf(velocidad_lineal + ACELERACION * delta, VELOCIDAD_MAX_DELANTE)
	else:
		# Sin input: fricción y arrastre.
		var freno := RESISTENCIA + absf(velocidad_lineal) * 0.6
		velocidad_lineal = move_toward(velocidad_lineal, 0.0, freno * delta)


func _aplicar_direccion(delta: float, izquierda: bool, derecha: bool) -> void:
	if not izquierda and not derecha:
		return
	if absf(velocidad_lineal) < 0.3:
		return
	var entrada := 0.0
	if izquierda:
		entrada += 1.0
	if derecha:
		entrada -= 1.0
	# Menor giro a alta velocidad; en marcha atrás la dirección se invierte.
	var velocidad_ratio := clampf(absf(velocidad_lineal) / VELOCIDAD_MAX_DELANTE, 0.0, 1.0)
	var giro := lerpf(GIRO_MAX, GIRO_MIN, velocidad_ratio)
	rotate_y(entrada * giro * signf(velocidad_lineal) * delta)


func alternar_camara() -> void:
	camara_exterior_activa = not camara_exterior_activa
	camara_interior.current = not camara_exterior_activa
	camara_exterior.current = camara_exterior_activa


func velocidad_kmh() -> float:
	return absf(velocidad_lineal) * 3.6
