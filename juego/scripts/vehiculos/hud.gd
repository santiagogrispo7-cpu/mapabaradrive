extends CanvasLayer
## Muestra la velocidad del vehículo en km/h y la cámara activa.

@onready var etiqueta_velocidad: Label = $EtiquetaVelocidad
@onready var etiqueta_camara: Label = $EtiquetaCamara

var _vehiculo: Node = null


func _ready() -> void:
	_vehiculo = get_tree().get_first_node_in_group("vehiculo")


func _process(_delta: float) -> void:
	if _vehiculo == null or not is_instance_valid(_vehiculo):
		_vehiculo = get_tree().get_first_node_in_group("vehiculo")
		if _vehiculo == null:
			return
	etiqueta_velocidad.text = "%d km/h" % int(round(_vehiculo.velocidad_kmh()))
	if _vehiculo.camara_exterior_activa:
		etiqueta_camara.text = "Cámara: exterior (C)"
	else:
		etiqueta_camara.text = "Cámara: interior (C)"
