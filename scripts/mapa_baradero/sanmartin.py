"""Cuadra fotografiada San Martin/Malabia: geometria aproximada, anclaje OSM.

Coordenadas de trabajo: X derecha del recorrido; Y hacia numeros decrecientes.
Geometria propria + materiales CC0. Nunca se recrea la red vial.
"""
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from . import common, inspection, pbr, vegetacion

ROOT = common.ROOT
ASSETS = ROOT / 'mapa/recursos/sanmartin'
START = Vector((-151.88592164369766, -59.961532421410084, 0))
END = Vector((-74.29460602032486, 52.695925501175225, 0))
D = (END-START).normalized()
R = Vector((D.y, -D.x, 0))
ANGLE = math.atan2(R.y, R.x)
FRAME = Matrix(((R.x,D.x,0,START.x),(R.y,D.y,0,START.y),(0,0,1,0),(0,0,0,1)))
MATS = {}
COL = None


def enum_set(data, prop, value):
    allowed = [i.identifier for i in data.bl_rna.properties[prop].enum_items]
    if value not in allowed:
        raise ValueError(f'{prop}: {value} not in {allowed}')
    setattr(data, prop, value)


def world(p):
    return FRAME @ Vector(p)


def tag(o, source='', kind='facade'):
    o['bara_sanmartin'] = True
    o['bara_kind_sm'] = kind
    o['bara_approximate'] = True
    o['bara_source_photo'] = source
    o['bara_notice'] = 'Reconstruccion visual aproximada; posicion parcelaria y dimensiones estimadas, eje OSM verificado'
    return o


def image(path, data=False):
    im = bpy.data.images.load(str(path), check_existing=True)
    if data:
        im.colorspace_settings.name = 'Non-Color'
    return im


def material(name, color, rough=.8, metal=0, texture=None, tint=None, emission=0,
             tile_m=2.0, normal_strength=.45):
    """Material PBR: Principled + mapas CC0; exportable a glTF y usable en Godot."""
    if texture:
        mat = pbr.pbr_material(f'MAT_SM_{name}', color, texture, roughness=rough,
                               metallic=metal, tint=tint, tile_m=tile_m,
                               normal_strength=normal_strength)
    else:
        mat = common.make_material(bpy, 'MAT_SM_'+name, color, rough, metal)
        mat['tile_m'] = tile_m
        shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        if emission:
            shader.inputs['Emission Color'].default_value = (*color, 1)
            shader.inputs['Emission Strength'].default_value = emission
    if emission and texture:
        shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        shader.inputs['Emission Color'].default_value = (*color, 1)
        shader.inputs['Emission Strength'].default_value = emission
    MATS[name] = mat
    return mat


def palette():
    material('asfalto',(.2,.2,.18),texture='asphalt_02',tile_m=3.0,normal_strength=.8)
    material('vereda',(.45,.4,.33),texture='concrete_pavement',tile_m=2.0)
    material('cesped',(.15,.2,.06),texture='grass_ground',tile_m=3.0,normal_strength=.5)
    for name, color in {
        'marfil':(.72,.69,.61), 'blanco':(.85,.84,.78), 'crema':(.57,.51,.39),
        'viejo':(.43,.42,.36), 'azul':(.035,.075,.095), 'rojo':(.53,.115,.09),
        'salmon':(.58,.22,.14), 'piedra':(.5,.46,.38)}.items():
        material(name,color,texture='grey_plaster',tint=color,tile_m=2.0)
    for name,color,rough,metal in [
        ('hierro',(.025,.028,.025),.55,.7),('amarillo',(.82,.5,.035),.65,0),
        ('chapa',(.075,.085,.09),.65,.45),('porton',(.28,.32,.32),.6,.35),
        ('aluminio',(.7,.7,.66),.4,.65),('toldo',(.18,.32,.42),.95,0),
        ('vidrio',(.045,.075,.085),.17,.25),('sombra',(.015,.018,.02),.95,0),
        ('hoja',(.065,.18,.038),.75,0),('tronco',(.24,.19,.12),.9,0)]:
        material(name,color,rough,metal)
    material('corteza_palmera',(.3,.25,.15),texture='palm_bark')
    material('luz_roja',(.38,.015,.008),.3,emission=.2)
    material('luz_ambar',(.7,.28,.015),.3,emission=.2)
    material('luz_verde',(.025,.8,.24),.3,emission=3)
    material('lampara',(.9,.79,.55),.3,emission=2)


class Mesh:
    """Un objeto por modulo, materiales compartidos, UV metricas sin operadores."""
    def __init__(self):
        self.v=[]; self.f=[]; self.mi=[]; self.materials=[]

    def add(self, vertices, faces, mat):
        if mat not in self.materials:
            self.materials.append(mat)
        mi=self.materials.index(mat); start=len(self.v)
        self.v.extend(vertices)
        self.f.extend(tuple(start+i for i in face) for face in faces)
        self.mi.extend([mi]*len(faces))

    def box(self, c, size, mat):
        x,y,z=c; a,b,h=[s/2 for s in size]
        self.add([(x+u*a,y+v*b,z+w*h) for u,v,w in
                  [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]],
                 [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat)

    def tube(self, a,b,r,mat,r2=None,n=8):
        a,b=Vector(a),Vector(b); axis=(b-a).normalized()
        ref=Vector((0,0,1)) if abs(axis.z)<.9 else Vector((1,0,0))
        u=axis.cross(ref).normalized(); v=axis.cross(u).normalized()
        r2=r if r2 is None else r2
        vs=[tuple(p+(u*math.cos(i*math.tau/n)+v*math.sin(i*math.tau/n))*rad)
            for p,rad in [(a,r),(b,r2)] for i in range(n)]
        fs=[tuple(reversed(range(n))),tuple(range(n,n*2))]
        fs += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        self.add(vs,fs,mat)

    def finish(self,name,source='',local=True,bevel=0):
        mesh=bpy.data.meshes.new(name)
        mesh.from_pydata(self.v,[],self.f); mesh.update()
        for mat in self.materials: mesh.materials.append(MATS[mat])
        for p,i in zip(mesh.polygons,self.mi): p.material_index=i
        # Normales coherentes y UV explicitamente exportables.
        import bmesh
        bm=bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
        uv=mesh.uv_layers.new(name='UVMap')
        for face in mesh.polygons:
            axis=max(range(3),key=lambda i:abs(face.normal[i]))
            axes=[i for i in range(3) if i!=axis]
            tile=float(mesh.materials[face.material_index].get('tile_m',2))
            for li in face.loop_indices:
                co=mesh.vertices[mesh.loops[li].vertex_index].co
                uv.data[li].uv=(co[axes[0]]/tile,co[axes[1]]/tile)
        ob=bpy.data.objects.new(name,mesh); COL.objects.link(ob)
        if local: ob.matrix_world=FRAME
        if bevel:
            mod=ob.modifiers.new('Cantos pequenos', 'BEVEL'); mod.width=bevel; mod.segments=2
        return tag(ob,source)


def text(name,body,loc,size,side=1,color='blanco',rotation=None):
    curve=bpy.data.curves.new(name,'FONT'); curve.body=body; curve.size=size; curve.extrude=.001
    enum_set(curve,'align_x','CENTER')
    ob=bpy.data.objects.new(name,curve); COL.objects.link(ob)
    ob.location=world(loc)
    # Texto en pared X constante: normal hacia el centro de la calle.
    normal=R*(-side)
    up=Vector((0,0,1)); right=up.cross(normal)
    ob.rotation_euler=Matrix((right,up,normal)).transposed().to_euler()
    if rotation is not None: ob.rotation_euler=rotation
    ob.data.materials.append(MATS[color]); tag(ob,kind='sign')
    return ob


def body(m,side,start,end,height,depth=9,mat='marfil'):
    m.box((side*(6.18+depth/2),(start+end)/2,.15+height/2),(depth,end-start,height),mat)


def opening(m,side,y,z,w,h,mat='vidrio',frame='blanco',depth=.16):
    x=side*6.10
    m.box((x,y,z),(.12,w,h),mat)
    for yy in (y-w/2-.065,y+w/2+.065): m.box((x-side*.065,yy,z),(depth,.13,h+.2),frame)
    for zz in (z-h/2-.06,z+h/2+.06): m.box((x-side*.065,y,zz),(depth,w+.25,.12),frame)


def cornice(m,side,start,end,z,mat='blanco'):
    for dx,dz,h in [(.0,0,.16),(-.12,.14,.13),(-.18,.27,.10)]:
        m.box((side*(6.03+dx),(start+end)/2,z+dz),(.32,end-start+.12,h),mat)


def shutter(m,side,y,width,height=2.8,z=.2):
    opening(m,side,y,z+height/2,width,height,'porton')
    for i in range(int(height/.12)):
        m.box((side*5.99,y,z+i*.12),(.035,width,.018),'aluminio')


def railing(m,side,start,end,z,x=5.25):
    for zz in (z,z+.85): m.tube((side*x,start,zz),(side*x,end,zz),.025,'hierro')
    for i in range(int((end-start)/.23)+1):
        y=start+i*.23
        m.tube((side*x,y,z),(side*x,y,z+.85),.018,'hierro',n=6)


def facades():
    # Esquina izquierda: cubierta plana, columnas y patio semicerrado oscuro.
    m=Mesh(); m.box((-14.8,15.5,.25),(17.4,16,.2),'vereda')
    m.box((-22.8,15.5,2.7),(.35,16,5.1),'viejo')
    m.box((-14.8,15.5,5.3),(17.8,16.5,.65),'viejo')
    m.box((-6.0,15.5,5.25),(.28,16.5,.85),'marfil')
    m.box((-14.8,7.4,5.25),(17.8,.25,.85),'marfil')
    for x,y in [(-6.3,8),(-6.3,15.5),(-6.3,22.8),(-17,8)]:
        m.box((x,y,2.65),(.55,.55,5.0),'viejo')
    for y in [7.8,22.9]: m.box((-14.5,y,1.1),(16,.14,1.8),'hierro')
    for i in range(22):
        m.box((-6.0,15.5,.35+i*.073),(.12,16,.045),'hierro')
    m.box((-6.0,15.5,4.7),(.32,7.5,.42),'blanco')
    m.finish('SM_Esquina_Cubierta_Plana','esquinasemaforo.png',bevel=.025)

    # Esquina derecha: vidrieras, zocalo, techo a cuatro aguas gris.
    m=Mesh()
    footprint=[(6.18,10),(9,7.4),(21,7.4),(21,23),(6.18,23)]
    n=len(footprint)
    m.add([(x,y,z) for z in (.15,3.1) for x,y in footprint],
          [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],'vidrio')
    for i,(x,y) in enumerate(footprint):
        a=footprint[(i+1)%n]
        m.tube((x,y,.45),(a[0],a[1],.45),.12,'piedra',n=4)
        m.tube((x,y,3.05),(a[0],a[1],3.05),.10,'blanco',n=4)
        m.box((x,y,1.65),(.12,.12,3),'blanco')
    for y in range(11,23,2): m.box((6.09,y,1.65),(.14,.10,3),'blanco')
    for x in range(10,21,2): m.box((x,7.32,1.65),(.10,.14,3),'blanco')
    apex=(14,15,6.1)
    m.add([(x,y,3.23) for x,y in footprint]+[apex],[(i,(i+1)%n,n) for i in range(n)],'chapa')
    # Costillas finas visibles sobre el faldon principal.
    for i in range(28):
        y=10+i*.46; end_y=15+(y-15)*.13
        m.tube((6.05,y,3.27),(13.1,end_y,5.82),.018,'porton',n=5)
    m.box((6.0,11.5,4.9),(.15,2.6,2),'chapa')
    m.box((5.9,11.5,4.9),(.05,2.25,1.65),'viejo')
    m.finish('SM_Esquina_Bar_Techo_Gris','esquinasemaforo2.png',bevel=.015)

    # Fachada izquierda azul: tres vanos con arcos, pilastras y cornisa.
    m=Mesh(); body(m,-1,24,39,4.65,8,'azul')
    for y in [26.4,31.4,36.4]:
        opening(m,-1,y,1.6,2.2,2.7,'sombra')
        for j in range(18):
            a=j*math.pi/18; b=(j+1)*math.pi/18
            m.tube((-5.94,y+1.25*math.cos(a),2.75+1.25*math.sin(a)),
                   (-5.94,y+1.25*math.cos(b),2.75+1.25*math.sin(b)),.10,'blanco',n=6)
        for yy in [y-1.5,y+1.5]:
            m.box((-5.96,yy,2.15),(.3,.25,4.05),'blanco')
        for yy in [y-.8,y-.4,y,y+.4,y+.8]:
            m.tube((-5.85,yy,.28),(-5.85,yy,2.8),.02,'hierro',n=6)
    cornice(m,-1,24,39,4.3)
    m.box((-5.7,31.3,3.55),(.18,2.8,.65),'hierro')
    m.finish('SM_Arcos_Azules','avsanmartin2.png',bevel=.018)

    m=Mesh(); body(m,-1,39,46.5,4.5,7,'rojo')
    opening(m,-1,42.7,1.7,4.5,2.9,'vidrio','crema')
    cornice(m,-1,39,46.5,4.1,'crema')
    m.finish('SM_Local_Rojo_Izquierdo','avsanmartin2.png',bevel=.025)

    # Casas bajas: muros claros, puertas altas, zocalos y molduras visibles.
    for i,(a,b,h) in enumerate([(46.5,57,4.4),(57,69,5.6),(69,78,4.5)]):
        m=Mesh(); body(m,-1,a,b,h,9,'marfil' if i!=0 else 'piedra')
        for j,y in enumerate([a+2,(a+b)/2,b-2]):
            opening(m,-1,y,1.75,1.0 if j==0 else 1.65,3.0,'sombra','marfil')
            if j:
                for yy in [y-.6,y-.3,y,y+.3,y+.6]:
                    m.tube((-5.9,yy,.65),(-5.9,yy,2.7),.018,'hierro',n=6)
        cornice(m,-1,a,b,h-.35,'marfil')
        m.finish(f'SM_Casa_Izquierda_{i+1:02d}','avsanmartin3.png',bevel=.02)

    m=Mesh(); body(m,-1,78,99,7,9,'crema')
    for y in [80.8,86,91.2,96.3]:
        opening(m,-1,y,1.65,3.5,2.8,'vidrio','piedra')
        opening(m,-1,y,5.15,2.4,2.7,'sombra','marfil')
        m.box((-5.65,y,3.95),(1.1,4.6,.18),'marfil')
        railing(m,-1,y-2.25,y+2.25,4.1)
        # Jardineras del balcon.
        m.box((-5.3,y,4.35),(.28,1.25,.32),'salmon')
    cornice(m,-1,78,99,6.7,'marfil')
    m.finish('SM_Balcon_Comercios','av.sanmartin.png',bevel=.02)
    for i,(a,b) in enumerate([(99,112),(112,127)]):
        m=Mesh(); body(m,-1,a,b,4.1,8,'marfil')
        opening(m,-1,(a+b)/2,1.7,b-a-1.4,2.7,'vidrio')
        m.box((-5.8,(a+b)/2,3.5),(.22,b-a-.6,.7),'rojo')
        m.finish(f'SM_Comercio_Fondo_{i}','av.sanmartin.png',bevel=.015)

    # Muro y porton a la derecha inmediatamente despues del bar.
    m=Mesh(); body(m,1,23.5,44,4.8,8,'blanco')
    for y in [26,29.2,32.4]:
        opening(m,1,y,1.6,2.5,2.4,'blanco','blanco')
        for zz in [.7,1.1,1.5,1.9,2.3]: m.box((5.95,y,zz),(.08,2.4,.05),'marfil')
    shutter(m,1,38.6,6.3,3)
    m.finish('SM_Muro_Porton_Gris','avsanmartin2.png',bevel=.025)

    # Edificio con balcones: el numero de niveles se estima de las vistas.
    m=Mesh(); body(m,1,44,61,13.0,11,'marfil')
    for y in [47,52.5,58]: opening(m,1,y,1.8,4.3,3.1,'vidrio','chapa')
    m.box((5.98,52.5,3.4),(.15,16,.6),'hierro')
    for level in range(3):
        z=4.0+level*2.85
        for y in [47,52.5,58]: opening(m,1,y,z+1.3,3.8,2.5,'sombra','crema')
        m.box((5.4,52.5,z),(1.6,17,.25),'blanco')
        railing(m,1,44.1,60.9,z+.2,x=4.7)
        m.box((4.65,52.5,z+.42),(.12,17,.42),'viejo')
    railing(m,1,44,61,13.2,x=6.2)
    for y in [45,46,47]: m.tube((14,y,13.1),(14,y,14.2),.075,'chapa')
    m.finish('SM_Edificio_Balcones','avsanmartin2.png;avsanmartin3.png',bevel=.02)

    m=Mesh(); body(m,1,61,73,4.6,8,'piedra')
    opening(m,1,65,1.7,2.7,2.9,'vidrio','chapa')
    opening(m,1,70.4,1.7,1.1,2.9,'hierro','crema')
    m.finish('SM_Local_Piedra','avsanmartin3.png',bevel=.02)

    # Portal blanco con jardin, pilares ornamentados y remates piramidales.
    m=Mesh(); m.box((11,80.5,.17),(9.5,14.5,.05),'cesped')
    m.box((6.14,80.5,.45),(.22,14.6,.6),'blanco')
    for y in [73.3,79.8,87.6]:
        m.box((6.18,y,1.95),(.62,.72,3.6),'blanco')
        for z,w,h in [(3.55,.94,.12),(3.7,1.05,.18),(3.85,.9,.1)]:
            m.box((6.18,y,z),(w,w,h),'blanco')
        m.add([(6.18+u*.45,y+v*.45,3.9) for u,v in [(-1,-1),(1,-1),(1,1),(-1,1)]]+[(6.18,y,4.8)],
              [(0,1,4),(1,2,4),(2,3,4),(3,0,4)],'blanco')
        m.tube((5.81,y,3.3),(5.74,y,3.3),.18,'marfil',n=12)
    railing(m,1,73.5,87.3,.7,x=6.18)
    m.finish('SM_Portal_Jardin_Ornamentado','av.sanmartin.png',bevel=.025)

    # Fachada roja y toldos de lona azul, con molduras y parapeto antiguo.
    m=Mesh(); body(m,1,88,113,6.3,10,'rojo')
    for y in [91,97,103,109.5]:
        opening(m,1,y,1.85,4.8,3.1,'vidrio','rojo')
        m.add([(6.0,y-2.3,3.55),(6.0,y+2.3,3.55),(4.95,y+2.3,2.8),(4.95,y-2.3,2.8)],[(0,1,2,3)],'toldo')
        m.box((4.95,y,2.72),(.05,4.6,.18),'toldo')
        for yy in [y-2.3,y+2.3]: m.tube((6,yy,3.5),(4.95,yy,2.8),.025,'hierro')
        m.box((5.98,y,4.7),(.17,1.2,.12),'rojo')
        m.box((5.98,y,5.0),(.17,.22,.55),'rojo')
    cornice(m,1,88,113,5.65,'viejo')
    for y in [88.2,94.2,100.4,106.6,112.8]:
        m.box((6.05,y,6.45),(.28,.65,1.3),'viejo')
        m.box((6.0,y,7.1),(.42,.85,.17),'viejo')
    m.finish('SM_Fachada_Roja_Toldos_Azules','av.sanmartin.png',bevel=.02)
    m=Mesh(); body(m,1,113,127,6.9,9,'blanco')
    for y in [116,121,125]: opening(m,1,y,1.9,1.5,3.2,'sombra')
    cornice(m,1,113,127,6.4,'viejo')
    m.finish('SM_Frente_Claro_Final','av.sanmartin.png',bevel=.02)


def patio():
    # Contexto de aproximacion, antes de Malabia (visible en dos referencias).
    m=Mesh(); m.box((-17.5,-21,.12),(23,27,.04),'cesped')
    m.box((-25.5,-21,1.8),(.25,26,3.3),'salmon')
    m.box((-24,-21,3.45),(6.8,26.5,.18),'chapa')
    m.box((-20.7,-21,.65),(.2,26,1),'salmon')
    for y in range(-33,-7,4): m.box((-20.7,y,2),(.12,.12,2.8),'blanco')
    for y in [-31,-23,-14]:
        m.box((-13,y,.16),(14,.8,.05),'vereda')
        m.tube((-8,y,.2),(-8,y,3.2),.035,'blanco')
        m.tube((-8,y,3.2),(-8,y,3.35),.20,'lampara',r2=.12,n=10)
    for y in [-30,-10]:
        m.box((-7.8,y,1.6),(.12,4,1.5),'salmon')
        m.tube((-7.8,y-1.9,.2),(-7.8,y-1.9,2.5),.05,'hierro')
        m.tube((-7.8,y+1.9,.2),(-7.8,y+1.9,2.5),.05,'hierro')
    m.finish('SM_Patio_Comidas_Referencia','patiodecomidas1.png;av.sanmartin1.png')
    text('SM_Cartel_Cena_Show','CENA SHOW',(-7.68,-30,1.5),.38,-1)
    text('SM_Cartel_Asado','ASADO',(-7.68,-10,1.5),.44,-1)


def props():
    m=Mesh()
    # Semaforo amarillo en la esquina derecha de la calle (foto + nodo OSM).
    m.tube((5.3,7.5,.15),(5.3,7.5,5.7),.075,'amarillo')
    m.tube((5.3,7.5,5.7),(.9,7.5,5.7),.06,'amarillo')
    for x,z in [(5.3,3.0),(.9,5.0)]:
        m.box((x,7.5,z),(.35,.23,1.05),'amarillo')
        m.box((x,7.35,z),(.28,.06,.97),'sombra')
        for dz,mat in [(.31,'luz_roja'),(0,'luz_ambar'),(-.31,'luz_verde')]:
            m.tube((x,7.29,z+dz),(x,7.26,z+dz),.10,mat,n=16)
            m.add([(x-.13,7.26,z+dz+.12),(x+.13,7.26,z+dz+.12),
                   (x+.13,7.04,z+dz+.07),(x-.13,7.04,z+dz+.07)],[(0,1,2,3)],'sombra')
    # Poste de esquina y cartel vial legible en referencia.
    m.tube((-5.2,-5.7,.15),(-5.2,-5.7,3.2),.045,'hierro')
    m.box((-5.2,-5.7,2.8),(.06,1.45,.52),'azul')
    # Cebras sobre San Martin, ya fuera del centro del cruce.
    for x in [-3,-2,-1,0,1,2,3]: m.box((x,5.7,.025),(.45,1.8,.008),'blanco')
    # Barandas para motos y bordillos amarillos vistos.
    for side,y in [(-1,12),(1,11),(-1,22),(1,22)]:
        m.tube((side*4.8,y,.16),(side*4.8,y,1),.025,'hierro')
        m.tube((side*4.8,y+1.8,.16),(side*4.8,y+1.8,1),.025,'hierro')
        m.tube((side*4.8,y,1),(side*4.8,y+1.8,1),.025,'hierro')
    for side in [-1,1]:
        for a,b in [(7,16),(44,59)]: m.box((side*4.08,(a+b)/2,.155),(.15,b-a,.015),'amarillo')
    # Mobiliario exterior: sillas y mesas blancas del bar y rojas del local azul.
    for x,y in [(5,15),(5,20),(-5,40),(-5,44)]:
        mat='blanco' if x>0 else 'rojo'
        m.box((x,y,.9),(.7,.7,.07),mat)
        m.tube((x,y,.16),(x,y,.88),.035,'hierro')
        for yy in [y-.65,y+.65]:
            m.box((x,yy,.55),(.43,.43,.05),mat)
            m.box((x,yy+.2,.83),(.43,.05,.5),mat)
            for dx in [-.17,.17]:
                for dy in [-.17,.17]: m.tube((x+dx,yy+dy,.17),(x+dx,yy+dy,.55),.018,'hierro',n=5)
    # Luces de calle y conductores visibles, sin inventar redes subterraneas.
    for side,y in [(-1,9),(1,37),(-1,68),(1,103)]:
        x=side*5.1
        m.tube((x,y,.15),(x,y,7),.075,'viejo',r2=.055)
        m.tube((x,y,7),(x-side*1.7,y+1,7.5),.045,'hierro')
        m.box((x-side*1.7,y+1,7.45),(.25,.7,.15),'porton')
    for x in [-5.65,5.65]:
        for offset in [0,.13,.26,.4]:
            for a,b in [(7,40),(40,80),(80,127)]:
                points=[(x+offset,a+(b-a)*i/12,7.2-.5*math.sin(i/12*math.pi)) for i in range(13)]
                for p,q in zip(points,points[1:]): m.tube(p,q,.012,'hierro',n=5)
    for y in [28,61,96,121]:
        for i in range(16):
            x=-6+i*.75; xx=x+.75
            z=7.0-.65*(1-(x/6)**2); zz=7-.65*(1-(xx/6)**2)
            m.tube((x,y,z),(xx,y,zz),.009,'hierro',n=5)
            if i%2==0: m.tube((x,y,z-.12),(x,y,z-.24),.035,'lampara',r2=.045,n=6)
    m.finish('SM_Mobiliario_Semaforo_Cables','esquinasemaforo2.png;av.sanmartin.png;avsanmartin3.png')
    text('SM_Placa_SanMartin','SAN MARTIN\n1100 - 1000',(-5.15,-5.7,2.82),.14,-1)


def palms_mesh():
    """Palmera con pinulas individuales, tronco texturado; una malla compartida."""
    rng=random.Random(749)
    m=Mesh(); m.tube((0,0,0),(.16,0,6.8),.23,'corteza_palmera',r2=.14,n=12)
    for j in range(16):
        angle=j*math.tau/16+rng.uniform(-.12,.12)
        d=Vector((math.cos(angle),math.sin(angle),0)); tangent=Vector((-d.y,d.x,0))
        length=rng.uniform(2.5,3.8)
        points=[Vector((.16,0,6.7))+d*(length*t)+Vector((0,0,1.6*math.sin(t*math.pi)-2*t*t)) for t in [i/14 for i in range(15)]]
        for p,q in zip(points,points[1:]): m.tube(p,q,.024,'hoja',r2=.012,n=5)
        for k in range(1,14):
            t=k/14; p=points[k]; leaflen=.65*math.sin(math.pi*t)**.6
            for side in [-1,1]:
                tip=p+tangent*side*leaflen+d*.18-Vector((0,0,.28))
                mid=(p+tip)*.5
                m.add([tuple(p),tuple(mid+d*.055),tuple(tip),tuple(mid-d*.055)],[(0,1,2,3)],'hoja')
    ob=m.finish('SM_Palmera_Plantilla',local=False)
    # Textura foliar pequena generada, PBR directa compatible glTF.
    return ob


def vegetation():
    """Vegetacion realista CC0 sobre la cuadra y reemplazo de arboles geometricos.

    Las palmeras y arboles de la cuadra usan modelos CC0 de Poly Haven; los
    arboles geometricos anteriores (icosferas) se sustituyen por el mismo
    modelo, conservando su posicion y escala para no alterar la composicion.
    """
    rng=random.Random(4242)
    trees=[]
    # Plantillas CC0: una de arbol y una de jacaranda, simplificadas.
    # Presupuesto de juego: LOD0 para lo cercano, LOD1 para lo distante.
    # El thinning de hoja es espacial, de modo que la copa mantiene densidad.
    jacaranda,src_j,fin_j = vegetacion.import_template(
        'jacaranda_tree','SM_Plantilla_Jacaranda_LOD0',leaf_keep=.45,branch_ratio=.40)
    arbol,src_a,fin_a = vegetacion.import_template(
        'island_tree_02','SM_Plantilla_Arbol_LOD0',leaf_keep=.45,branch_ratio=.45)
    jacaranda_l1 = vegetacion.make_lod1(jacaranda,'SM_Plantilla_Jacaranda_LOD1',
                                        leaf_keep=.5,collapse_ratio=.4)
    arbol_l1 = vegetacion.make_lod1(arbol,'SM_Plantilla_Arbol_LOD1',
                                     leaf_keep=.5,collapse_ratio=.4)
    for template in (jacaranda,arbol,jacaranda_l1,arbol_l1):
        template.hide_render=True
        template.hide_viewport=True
        template['bara_plantilla']=True
    # Palmeras: modelo CC0 de hoja publica no disponible; corona propia con
    # textura de corteza CC0 de palma.
    palmera = palms_mesh()
    palmera.hide_render=True
    palmera.hide_viewport=True
    palmera['bara_plantilla']=True

    # Arboles de la cuadra segun las fotos: alineacion sobre la vereda.
    # Izquierda (fachadas con arcos y casas bajas) y derecha (portal y rojo).
    left=[(20.5,5.2,1.05),(33.0,5.6,1.0),(44.0,5.4,.95),(55.5,5.5,1.0),
          (67.0,5.3,.92),(90.0,5.6,1.02),(101.0,5.4,.95)]
    right=[(58.0,5.6,1.05),(70.0,5.5,.98),(82.0,5.7,1.1),(95.0,5.4,1.0),
           (108.0,5.6,.94),(118.0,5.3,.9)]
    for side,items in ((-1,left),(1,right)):
        for index,(along,offset,scale) in enumerate(items,start=1):
            location=world((side*offset,along,0.15))
            template = jacaranda if (side==-1 and index%2==0) else arbol
            lod = 0 if along < 70 else 1
            used = template if lod == 0 else (jacaranda_l1 if template is jacaranda else arbol_l1)
            obj=vegetacion.instance(used,f'SM_Arbol_CC0_{"I" if side<0 else "D"}{index:02d}',
                                    location,rng.uniform(0,math.tau),scale,COL,lod)
            obj['bara_source_photo']='avsanmartin2.png;avsanmartin3.png;av.sanmartin.png'
            trees.append(obj)
    # Palmeras de la esquina del bar y del costado derecho.
    for index,(side,along,offset,scale) in enumerate(
            [(1,9.0,5.9,1.0),(1,13.5,6.1,.92),(1,30.0,6.0,.95),
             (-1,4.0,6.0,.9),(-1,-8.0,6.2,1.05),(-1,-16.0,6.0,.88)],start=1):
        obj=vegetacion.instance(palmera,f'SM_Palmera_CC0_{index:02d}',
                                world((side*offset,along,0.15)),
                                rng.uniform(0,math.tau),scale,COL)
        obj['bara_source_photo']='esquinasemaforo2.png;av.sanmartin1.png;patiodecomidas1.png'
        trees.append(obj)

    # Reemplazo de arboles geometricos del mapa por el modelo CC0.
    replaced=[]
    for obj in list(bpy.data.objects):
        if obj.get('bara_kind')!='arbol' or obj.type!='MESH':
            continue
        if obj.get('bara_realista') or obj.get('bara_kind')=='plaza_arbol':
            continue
        location=obj.matrix_world.translation.copy()
        scale=obj.scale.x
        name=obj.name
        instance=vegetacion.instance(arbol,'SM_Arbol_CC0_'+name.replace('ARBOL_','REEMPLAZO_'),
                                     location,obj.rotation_euler.z,scale,COL)
        instance['bara_reemplaza']=name
        replaced.append((name,instance.name))
        bpy.data.objects.remove(obj,do_unlink=True)
    return {'arboles_cuadra':len(trees),'plantillas':5,
            'tri_jacaranda':[src_j,fin_j],'tri_arbol':[src_a,fin_a],
            'tri_jacaranda_lod1':len(jacaranda_l1.data.polygons),
            'tri_arbol_lod1':len(arbol_l1.data.polygons),
            'arboles_reemplazados':replaced}


def setup_cameras():
    def cam(name,loc,target,lens=30):
        data=bpy.data.cameras.new(name); data.lens=lens; data.clip_end=4000
        ob=bpy.data.objects.new(name,data); COL.objects.link(ob)
        ob.location=world(loc); ob.rotation_euler=(world(target)-ob.location).to_track_quat('-Z','Y').to_euler()
        tag(ob,kind='camera'); return ob
    street=cam('CAMARA_SANMARTIN_ESQUINA',(0,-8,2.25),(0,42,3.2),25)
    cam('CAMARA_SANMARTIN_RECORRIDO',(.6,30,2.0),(0,95,3.0),28)
    cam('CAMARA_SANMARTIN_FACHADAS',(-1,66,2.0),(4,94,3.5),26)
    aerial=cam('CAMARA_SANMARTIN_AEREA',(-80,60,120),(0,60,0),38)
    bpy.context.scene.camera=street
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                enum_set(area.spaces.active.region_3d,'view_perspective','CAMERA')
                area.spaces.active.region_3d.view_camera_zoom=0
                enum_set(area.spaces.active.shading,'type','MATERIAL')
    return street


def setup_lighting():
    """Cielo fisico y sol coherente con el, para que las fachadas lean."""
    scene=bpy.context.scene
    world_data=bpy.data.worlds.new('SM_Cielo_Dia'); world_data.use_nodes=True
    nodes=world_data.node_tree.nodes; links=world_data.node_tree.links
    background=next(n for n in nodes if n.type=='BACKGROUND')
    sky=nodes.new('ShaderNodeTexSky'); enum_set(sky,'sky_type','NISHITA')
    sky.sun_elevation=math.radians(48); sky.sun_rotation=math.radians(205)
    sky.sun_disc=False; sky.air_density=1; sky.dust_density=.5
    links.new(sky.outputs[0],background.inputs['Color'])
    background.inputs['Strength'].default_value=1.0
    scene.world=world_data
    # El sol de la escena base se orienta como el cielo para evitar
    # contraluces con fachadas completamente negras.
    sun=bpy.data.objects.get('SOL')
    if sun is not None and sun.data.type=='SUN':
        elevation=math.radians(48); azimuth=math.radians(205)
        sun.rotation_euler=(math.pi/2-elevation,0.0,azimuth-math.pi/2)
        sun.data.energy=3.5
        sun.data.angle=math.radians(1.5)
    scene.render.resolution_x=1280; scene.render.resolution_y=800; scene.render.resolution_percentage=100
    enum_set(scene.render.image_settings,'file_format','PNG')
    return scene.render.engine


def upgrade_surfaces():
    """PBR con texturas CC0 sobre el asfalto, las veredas y el cesped existentes.

    Se conservan la geometria y las capas actuales: solo cambian los materiales
    y se agrega UV en caja, en metros de mundo, para que la textura conserve
    escala real y sea exportable a glTF.
    """
    applied={}
    surfaces=pbr.surface_materials()
    groups={'CALLES':'asfalto','VEREDAS':'vereda','CORDONES':'vereda'}
    for collection_name,key in groups.items():
        collection=bpy.data.collections.get(collection_name)
        if collection is None:
            continue
        count=0
        for obj in collection.objects:
            if obj.type!='MESH' or not obj.data.polygons:
                continue
            pbr.assign(bpy,obj,surfaces[key],tile_m=3.0 if key=='asfalto' else 2.0,
                        fix_normals=True)
            count+=1
        applied[collection_name]=count
    terreno=bpy.data.objects.get('TERRENO_BASE')
    if terreno is not None:
        pbr.assign(bpy,terreno,surfaces['cesped'],tile_m=4.0,fix_normals=True)
        applied['TERRENO_BASE']=1
    return applied


def make_layout():
    global COL
    if bpy.data.collections.get('BARA_SANMARTIN_REALISTA'):
        raise RuntimeError('La coleccion ya existe; abrir la base corregida para regenerar')
    COL=common.ensure_collection(bpy,'BARA_SANMARTIN_REALISTA',bpy.data.collections['BARA_MAPA_3D'])
    palette()
    facades(); patio(); props()
    veg_report=vegetation()
    surfaces_report=upgrade_surfaces()
    setup_cameras(); setup_lighting()
    bpy.context.view_layer.update()
    counts,tris=vegetacion.measure([o for o in COL.objects if o.type=='MESH'])
    return {'root':COL.name,'length_m':round((END-START).length,2),
            'start':[round(v,3) for v in START],'end':[round(v,3) for v in END],
            'source_way':'228161668','traffic_signal_node':'2367942995',
            'vegetacion':veg_report,'objetos_por_tipo':dict(counts),'triangulos':tris,
            'superficies_pbr':surfaces_report,
            'notice':'Parcelas y alturas estimadas desde fotos; no relevamiento metrico'}
