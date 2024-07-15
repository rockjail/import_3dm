# MIT License

# Copyright (c) 2018-2024 Nathan Letwory, Joel Putnam, Tom Svilans, Lukas Fertig

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import bpy
import rhino3dm as r3d
from . import utils
import bmesh
import bpy.app

import traceback


def import_render_mesh(context, ob, name, scale, options):
    # concatenate all meshes from all (brep) faces,
    # adjust vertex indices for faces accordingly
    # first get all render meshes
    og = ob.Geometry
    oa = ob.Attributes

    needs_welding = False

    msh_tex = list()
    if og.ObjectType == r3d.ObjectType.Extrusion:
        msh = [og.GetMesh(r3d.MeshType.Any)]
    elif og.ObjectType == r3d.ObjectType.Mesh:
        msh = [og]
    elif og.ObjectType == r3d.ObjectType.SubD:
        msh = [r3d.Mesh.CreateFromSubDControlNet(og, False)]
        msh_tex = [r3d.Mesh.CreateFromSubDControlNet(og, True)]
        # needs_welding = True
    elif og.ObjectType == r3d.ObjectType.Brep:
        msh = [og.Faces[f].GetMesh(r3d.MeshType.Any) for f in range(len(og.Faces)) if type(og.Faces[f])!=list]
    fidx = 0
    faces = []
    vertices = []
    coords = []

    # now add all faces and vertices to the main lists
    for m in msh:
        if not m:
            continue
        faces.extend([list(map(lambda x: x + fidx, m.Faces[f])) for f in range(len(m.Faces))])

        # Rhino always uses 4 values to describe faces, which can lead to
        # invalid faces in Blender. Tris will have a duplicate index for the 4th
        # value.
        for f in faces:
            if f[-1] == f[-2]:
                del f[-1]

        fidx = fidx + len(m.Vertices)
        vertices.extend([(m.Vertices[v].X * scale, m.Vertices[v].Y * scale, m.Vertices[v].Z * scale) for v in range(len(m.Vertices))])
        coords.extend([(m.TextureCoordinates[v].X, m.TextureCoordinates[v].Y) for v in range(len(m.TextureCoordinates))])

    mesh = context.blend_data.meshes.new(name=name)
    tags = utils.create_tag_dict(oa.Id, oa.Name)
    mesh = utils.get_or_create_iddata(context.blend_data.meshes, tags, None)
    mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)

    coords_tex = list()
    for mt in msh_tex:
        if not mt:
            continue
        coords_tex.extend([(mt.TextureCoordinates[v].X, mt.TextureCoordinates[v].Y) for v in range(len(mt.TextureCoordinates))])

    if mesh.loops:  # and len(coords) == len(vertices):
        # todo:
        # * check for multiple mappings and handle them
        # * get mapping name (missing from rhino3dm)
        # * rhino assigns a default mapping to unmapped objects, so if nothing is specified, this will be imported

        #create a new uv_layer and copy texcoords from input mesh
        mesh.uv_layers.new(name="RhinoUVMap")

        if sum(len(x) for x in faces) == len(mesh.uv_layers["RhinoUVMap"].data):
            uvl = mesh.uv_layers["RhinoUVMap"].data[:]

            for loop in mesh.loops:
                try:
                    if coords_tex:
                        uvl[loop.index].uv = coords_tex[loop.index]
                    elif coords:
                        # print(loop.index, loop.vertex_index, len(uvl), len(coords))
                        uvl[loop.index].uv = coords[loop.vertex_index]
                    else:
                        print("no tex coords")
                except Exception:  # TODO: narrow down error type, you lazy bastard ;)
                    print(name)
                    print(traceback.format_exc())

            mesh.validate()
            mesh.update()

        else:
            #in case there was a data mismatch, cleanup the created layer
            mesh.uv_layers.remove(mesh.uv_layers["RhinoUVMap"])



    if needs_welding:
        bm = bmesh.new()
        bm.from_mesh(mesh)

        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bm.to_mesh(mesh)
        bm.free()
        if bpy.app.version < (4, 1):
            mesh.use_auto_smooth = True
    # done, now add object to blender


    return mesh
