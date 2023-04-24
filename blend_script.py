import sys
import subprocess
import os

# Bootstrapping libraries

venv_site_pkg_file_path = os.path.join(os.getcwd(), '.venv/Lib/site-packages')

if not os.path.exists(venv_site_pkg_file_path):
    exe_file_path = sys.executable
    venv_file_path = os.path.join(os.getcwd(), '.venv')
    subprocess.run([exe_file_path, '-m' 'venv', venv_file_path])

    venv_exe_file_path = os.path.join(os.getcwd(), '.venv/Scripts/python.exe')
    venv_pip_file_path = os.path.join(os.getcwd(), '.venv/Scripts/pip.exe')

    subprocess.run([venv_pip_file_path, 'install', 'UnityPy'])

sys.path.append(venv_site_pkg_file_path)
import itertools, struct, uuid
import UnityPy
from UnityPy.enums import ClassIDType 
from UnityPy.files import ObjectReader, BundleFile
from UnityPy.files.SerializedFile import SerializedType
import os
from copy import copy

import bpy

root_obj = [obj for obj in bpy.data.objects if obj.parent == None][0]

obj_list = [None] * len(bpy.data.objects)
parent_index_list = [None] * len(bpy.data.objects)

obj_list[0] = root_obj
parent_index_list[0] = None # Already done but just to be explicit

index_list_counter = 0

def recursively_find_children(obj):
    child_count = len(obj.children)
    
    global index_list_counter

    parent_index_list[index_list_counter+1:index_list_counter+1+child_count] = [index_list_counter] * child_count
    obj_list[index_list_counter+1:index_list_counter+1+child_count] = obj.children
    
    index_list_counter += child_count

    for child in obj.children:
        recursively_find_children(child)

recursively_find_children(root_obj)

base_asset_file_path = os.path.join(os.getcwd(), 'base_bundle')
# base_asset_file_path = "C:/Program Files (x86)/Steam/Backups/TinyCombatArenaDev/Arena_Data/resources-original.assets"
saved_asset_file_path = os.path.join(os.getcwd(), 'output/created_bundle')
env = UnityPy.load(base_asset_file_path)

class EmptyBundle(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.__class__ = BundleFile
    
    def save(self):
        return self.data

def generate_16_byte_uid():
    return uuid.uuid1().urn[-16:].encode("ascii")

def get_next_id_gen():
    id = 2
    while True:
        yield id
        id += 1

id_gen = get_next_id_gen()

base_obj_dict = [obj for obj in env.objects if obj.type.name == 'GameObject'][0].__dict__

sf = list(env.file.files.values())[0]
keys = list(sf.objects.keys())
for key in keys:
    if sf.objects[key].type.name != 'AssetBundle':
        del sf.objects[key]

def get_type_id(class_id):
    type_id = -1
    for i, sftype in enumerate(sf.types):
        if sftype.class_id == class_id:
            type_id = i
    if type_id == -1:
        type_id = len(sf.types)
        print(True, type_id, class_id)
        sf.types.append(
            EmptySerializedType(
                class_id=class_id,
                is_stripped_type=False,
                node=[],
                script_type_index=-1,
                old_type_hash=generate_16_byte_uid(),
                string_data=b'',
                type_dependencies=[]
            )
        )
    return type_id


# asset bundle is at path_id 1 by default

class EmptyObject(object):
    def __init__(self, **kwargs):
        self.__dict__.update(base_obj_dict)
        self.__dict__.update(kwargs)
        self.__class__ = ObjectReader
        sf.objects[kwargs['path_id']] = self
        sf.mark_changed()

class EmptySerializedType(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.__class__ = SerializedType 


for blend_obj in obj_list:
    if blend_obj.type == 'EMPTY':
        empty_obj = EmptyObject(
            type_id=get_type_id(4),
            type=ClassIDType(4),
            serialized_type = sf.types[get_type_id(4)],
            class_id=4,
            data=b'',
            path_id=next(id_gen)
        )

        empty_obj.save_typetree({
            'm_GameObject': {
                'm_FileID': 0,
                'm_PathID': 0,
            },
            'm_LocalRotation': dict(zip([*'wxyz'], blend_obj.rotation_quaternion)),
            'm_LocalPosition': dict(zip([*'xyz'], blend_obj.location)),
            'm_LocalScale': dict(zip([*'xyz'], blend_obj.scale)),
            'm_Children': [],
            'm_Father': {
                'm_FileID': 0,
                'm_PathID': 0,
            },
        })
    elif blend_obj.type == 'MESH':
        byte_mask = (1 << 8) - 1
        to_bytes = lambda x: list(struct.pack('<f', x))

        empty_obj = EmptyObject(
            type_id=get_type_id(43),
            type=ClassIDType(43),
            serialized_type = sf.types[get_type_id(43)],
            class_id=43,
            data=b'',
            path_id=next(id_gen)
        )

        mesh=blend_obj.data

        positions = []
        normals = []
        uvs = []
        index_buffer = []
        index_counter = 0

        for poly in mesh.polygons:
            for i in range(poly.loop_start, poly.loop_start + 3):
                
                loop = mesh.loops[i]
                uv_loop = mesh.uv_layers[0].data[i]
                vert = mesh.vertices[loop.vertex_index]
                
                positions.append(vert.co)
                normals.append(poly.normal)
                uvs.append(uv_loop.uv)

                index_buffer += [index_counter & byte_mask, index_counter >> 8]
                index_counter += 1



        data_size: list[int] = []
        for vert in zip(positions, normals, uvs):
            data_size.extend(itertools.chain(*[to_bytes(float) for float in itertools.chain(*vert)]))


        empty_obj.save_typetree({
            'm_Name': blend_obj.name,
            'm_SubMeshes': [
                {
                    'firstByte': 0,
                    'indexCount': int(len(index_buffer) / 2),
                    'topology': 0,
                    'baseVertex': 0,
                    'firstVertex': 0,
                    'vertexCount': int(len(data_size) / 32),
                    'localAABB': {
                        'm_Center': dict(zip([*'xyz'], [0, 0, 0])),
                        'm_Extent': dict(zip([*'xyz'], [100, 100, 100]))
                    }
                }
            ],
            'm_Shapes': {
                'vertices': [],
                'shapes': [],
                'channels': [],
                'fullWeights': []
            },
            'm_BindPose': [],
            'm_BoneNameHashes': [],
            'm_RootBoneNameHash': 0,
            'm_BonesAABB': [],
            'm_VariableBoneCountWeights': {
                'm_Data': b''
            },
            'm_MeshCompression': 0,
            'm_IsReadable': True,
            'm_KeepVertices': False,
            'm_KeepIndices': False,
            'm_IndexFormat': 0,
            'm_IndexBuffer': index_buffer,
            'm_VertexData': {
                'm_VertexCount': int(len(data_size) / 32),
                'm_Channels': [
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 3},
                    {'stream': 0, 'offset': 12, 'format': 0, 'dimension': 3},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 24, 'format': 0, 'dimension': 2},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0},
                    {'stream': 0, 'offset': 0, 'format': 0, 'dimension': 0}
                ],
                'm_DataSize': bytes(data_size)
            },
            'm_CompressedMesh': {
                'm_Vertices': {
                    'm_NumItems': 0,
                    'm_Range': 0,
                    'm_Start': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_UV': {
                    'm_NumItems': 0,
                    'm_Range': 0,
                    'm_Start': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_Normals': {
                    'm_NumItems': 0,
                    'm_Range': 0,
                    'm_Start': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_Tangents': {
                    'm_NumItems': 0,
                    'm_Range': 0,
                    'm_Start': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_Weights': {
                    'm_NumItems': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_NormalSigns': {
                    'm_NumItems': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_TangentSigns': {
                    'm_NumItems': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_FloatColors': {
                    'm_NumItems': 0,
                    'm_Range': 0,
                    'm_Start': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_BoneIndices': {
                    'm_NumItems': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_Triangles': {
                    'm_NumItems': 0,
                    'm_Data': [],
                    'm_BitSize': 0
                },
                'm_UVInfo': 0
            },
            'm_LocalAABB': {
                'm_Center': dict(zip([*'xyz'], [0, 0, 0])),
                'm_Extent': dict(zip([*'xyz'], [100, 100, 100]))
            },
            'm_MeshUsageFlags': 0,
            'm_BakedConvexCollisionMesh': [],
            'm_BakedTriangleCollisionMesh': [],
            'm_MeshMetrics[0]': 0,
            'm_MeshMetrics[1]': 0,
            'm_StreamData': {
                'offset': 0,
                'size': 0,
                'path': ''
            }
        })
        
# for i, sftype in enumerate(sf.types):
#     print(i, sftype.__dict__)

with open(saved_asset_file_path, 'wb') as f:
    f.write(env.file.save())

# bundle = EmptyBundle(
#     signature="UnityFS",
#     version=7,
#     format=6,
#     version_engine="2020.3.30f1",
#     version_player="5.x.x",
#     files={},
# )

# bundle.files['serialized_files'] = env.file
# env.file.flags = 4
# env.file.externals = []

# with open('output/bundle.unity3d', 'wb') as file:
#     file.write(bundle.save())
