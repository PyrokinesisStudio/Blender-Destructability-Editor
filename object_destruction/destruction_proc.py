from bpy import types, props, utils, ops, data, path
from bpy.types import Object, Scene
from . import destruction_data as dd
from . import voronoi
import bpy
import os
import random
from bpy_extras import mesh_utils
from operator import indexOf
from mathutils import Vector, Quaternion, Euler, Matrix
import math
import bisect
import sys

#since a modification of fracture_ops is necessary, redistribute it
from . import fracture_ops as fo
imported = True
try: 
    from bpy.app.handlers import persistent
except ImportError:
    imported = False


#do the actual non-bge processing here

class Processor():
          
    def processDestruction(self, context):
           
        modes = {DestructionContext.destModes[0][0]: 
                    "self.applyFracture(context, objects, parts, roughness, crack_type)",
                 DestructionContext.destModes[1][0]: 
                     "self.applyExplo(context, objects, parts, granularity, thickness, False, False)",
                # DestructionContext.destModes[2][0]: 
                #     "self.applyExplo(context, objects, parts, granularity, thickness, True, True)",
                # DestructionContext.destModes[3][0]: 
                #     "self.applyExplo(context, objects, parts, granularity, thickness, True, False)",
                 DestructionContext.destModes[2][0]: 
                     "self.applyKnife(context, objects, parts, jitter, granularity, cut_type)",
                 DestructionContext.destModes[3][0]: 
                     "self.applyVoronoi(context, objects, parts, volume, True)",  
                 DestructionContext.destModes[4][0]: 
                     "self.applyVoronoi(context, objects, parts, volume, False)" } 
                     
        #make an object backup if necessary (if undo doesnt handle this)
        #according to mode call correct method
        mode = context.object.destruction.destructionMode
        parts = context.object.destruction.partCount
        granularity = context.object.destruction.pieceGranularity
        thickness = context.object.destruction.wallThickness
        destroyable = context.object.destruction.destroyable
        roughness = context.object.destruction.roughness
        crack_type = context.object.destruction.crack_type
        groundConnectivity = context.object.destruction.groundConnectivity
        cubify = context.object.destruction.cubify
        jitter = context.object.destruction.jitter
        cut_type = context.object.destruction.cut_type
        volume = context.object.destruction.voro_volume
        
        objects = []
        #determine HERE, which objects will be decomposed
        transMode = context.object.destruction.transmitMode
        if transMode == context.object.destruction.transModes[0][0]: #self
            sel = [o for o in context.selected_objects]
            for o in sel:
                if o != context.object:
                    o.select = False  
                      
            objects = [context.object]
            
        else:
            sel = [o for o in context.selected_objects]
            for o in sel:
                o.select = False
            
            for o in sel:
                o.select = True
                context.scene.objects.active = o
                if transMode == context.object.destruction.transModes[1][0]: #selected
                    objects.append(o)
                elif transMode == context.object.destruction.transModes[2][0] or \
                transMode == context.object.destruction.transModes[3][0]:
                    objects.append(o)
                    self.applyToChildren(o, objects, transMode)
                o.select = False
        
        if (parts > 1) or ((parts == 1) and cubify):
            print("OBJECTS: ", objects)   
            eval(modes[mode])
        
        return None
    
    
    def applyToChildren(self, ob, objects, transMode):
        for c in ob.children:
           if transMode == ob.destruction.transModes[3][0]:
               self.applyToChildren(c, objects, transMode) #apply recursively...
           objects.append(c)
           
               
    def createBackup(self, context, obj):
        
        sel = []
        for o in context.selected_objects:
            if o != obj:
                sel.append(o)
                o.select = False
                
        obj.select = True  
        context.scene.objects.active = obj
          
        ops.object.duplicate()
        backup = context.active_object
        backup.name = obj.name
        
        if len(backup.name.split(".")) == 1:
            backup.name += ".000"
        
#        if obj.destruction.keep_backup_visible:
#            backup.game.use_ghost = True
#        else:
        if obj.destruction.flatten_hierarchy or context.scene.hideLayer == 1:
            context.scene.objects.unlink(backup)
        print("Backup created: ", backup)
        
        for o in sel:
            o.select = True
        
        return backup
        
    def previewExplo(self, context, parts, thickness):
       
        print("previewExplo", parts, thickness)
        
        context.active_object.modifiers.new("Particle", 'PARTICLE_SYSTEM')
        context.active_object.modifiers.new("Explode", 'EXPLODE')
        
        if thickness > 0:
            
            context.active_object.modifiers.new("Solidify", 'SOLIDIFY')
            explode = context.active_object.modifiers[len(context.active_object.modifiers)-2]
            solidify = context.active_object.modifiers[len(context.active_object.modifiers)-1]
        
        else:
            explode = context.active_object.modifiers[len(context.active_object.modifiers)-1]
        
        #get modifier stackindex later, for now use a given order.
        settings = context.active_object.particle_systems[0].settings        
        settings.count = parts
        settings.frame_start = 2.0
        settings.frame_end = 2.0
        settings.distribution = 'RAND'
       
        explode.use_edge_cut = True
       
        if thickness > 0:
            solidify.thickness = thickness    
    
    def explo(self, context, obj, parts, granularity, thickness, massive, pairwise):
                   
        context.scene.objects.active = obj # context.object
        currentParts = [context.object.name]
        
        if granularity > 0:
            ops.object.mode_set(mode = 'EDIT')
            ops.mesh.subdivide(number_cuts = granularity)
            ops.object.mode_set()
        
        
#        if massive and pairwise:
#            while (len(currentParts) < parts):
#                oldnames = [o.name for o in context.scene.objects]
#                  #pick always the largest object to subdivide
#               # sizes = {}
#                #[self.dictItem(sizes, self.getSize(o), o.name) for o in context.scene.objects if o.name in currentParts]
#                    
#                #maxSize = max(sizes.keys())
#                #name = sizes[maxSize]
#                index = random.randint(0, len(currentParts)-1)
#                tocut = context.scene.objects[currentParts[index]]
#                context.scene.objects.active = tocut
#                parent = context.active_object.parent
#                
#                self.previewExplo(context, 2, 0) 
#                self.separateExplo(context, 0)   
#                
#                part = self.findNew(context, oldnames)[0].name
#                
#                ops.object.mode_set(mode = 'EDIT')
#                ops.mesh.select_all(action = 'SELECT')
#                ops.mesh.region_to_loop()
#                ops.mesh.fill()
#               # ops.mesh.edge_face_add()
#                #ops.mesh.quads_convert_to_tris()
#                ops.mesh.select_all(action = 'SELECT')
#                ops.mesh.normals_make_consistent()
#                ops.object.mode_set(mode = 'OBJECT')
#                tocut.select = True
#                ops.object.origin_set(type = 'ORIGIN_GEOMETRY')
#                tocut.select = False
#            
#                context.scene.objects.active = context.scene.objects[part]
#                ops.object.mode_set(mode = 'EDIT')
#                ops.mesh.select_all(action = 'SELECT')
#                ops.mesh.region_to_loop()
#                ops.mesh.fill()
#               # ops.mesh.edge_face_add()
#                #ops.mesh.quads_convert_to_tris()
#                ops.mesh.select_all(action = 'SELECT')
#                ops.mesh.normals_make_consistent()
#                ops.object.mode_set(mode = 'OBJECT')
#                context.active_object.select = True
#                ops.object.origin_set(type = 'ORIGIN_GEOMETRY')
#                context.active_object.select = False
#                
#                
#                currentParts.append(part)
#            
#        else:
            #explosion modifier specific    
        self.previewExplo(context, parts, thickness)
        self.separateExplo(context, thickness)
        
        for o in context.scene.objects:
            o.select = True
        ops.object.origin_set(type = 'ORIGIN_GEOMETRY')
        for o in context.scene.objects:
            o.select = False    
    
    def applyVoronoi(self, context, objects, parts , volume, wall):
        
        for obj in objects:
            print("applyVoronoi", obj,  parts, volume, wall)
            obj.destruction.wall = wall
            
            #prepare parenting
            parentName, nameStart, largest, bbox = self.prepareParenting(context, obj)
            backup = obj
            
           # print("LEN: ", len(backup.name.split(".")))
            if len(backup.name.split(".")) == 1:
                backup.name += ".000"
           # backup = self.createBackup(context, obj)
         
            if obj.destruction.cubify:
                self.cubify(context, obj, bbox, parts)
            else:
                voronoi.voronoiCube(context, obj, parts, volume, wall)
            
         #   if obj.destruction.keep_backup_visible:
        #        backup.game.use_ghost = True
         #   else:
            if obj.destruction.flatten_hierarchy or context.scene.hideLayer == 1:
                context.scene.objects.unlink(backup)
                    
            #do the parenting
            self.doParenting(context, parentName, nameStart, bbox, backup, largest, obj)     
    
        
    def applyExplo(self, context, objects, parts, granularity, thickness, massive, pairwise):
        #create objects from explo by applying it(or by loose parts)
        #check modifier sequence before applying it 
        #(if all are there; for now no other modifiers allowed in between)
        
        for obj in objects:
            print("applyExplo", obj,  parts, granularity, thickness)
            
            #prepare parenting
            parentName, nameStart, largest, bbox = self.prepareParenting(context, obj)
            backup = self.createBackup(context, obj)
            
            #if massive -> select all, region to loop, create faces, use self intersect
            #if massive and pairwise, apply a 2 piece particle system to random object
            #like knife
            if obj.destruction.cubify:
                self.cubify(context, obj, bbox, parts)
            else:
                self.explo(context, obj, parts, granularity, thickness, massive, pairwise)
                    
            #do the parenting
            self.doParenting(context, parentName, nameStart, bbox, backup, largest, obj) 
       
    
    def separateExplo(self, context, thickness): 
        
        explode = context.active_object.modifiers[len(context.active_object.modifiers)-1]
        if thickness > 0:
            explode = context.active_object.modifiers[len(context.active_object.modifiers)-2]
            solidify = context.active_object.modifiers[len(context.active_object.modifiers)-1]
        
        #if object shall stay together
        settings = context.active_object.particle_systems[0].settings  
        settings.physics_type = 'NO'
        settings.normal_factor = 0.0
        
        context.scene.frame_current = 2
       
        ctx = context.copy()
        ctx["object"] = context.active_object
        ops.object.modifier_apply(ctx, apply_as='DATA',  modifier = explode.name)
        
        if thickness > 0:
            ctx = context.copy()
            ctx["object"] = context.active_object
            ops.object.modifier_apply(ctx, apply_as='DATA', modifier = solidify.name)
        
        #must select particle system before somehow
        ctx = context.copy()
        ctx["object"] = context.active_object
        ops.object.particle_system_remove(ctx) 
        ops.object.mode_set(mode = 'EDIT')
        ops.mesh.select_all(action = 'DESELECT')
        #omit loose vertices, otherwise they form an own object!
        #ops.mesh.select_by_number_vertices(number = 3, type='LESS')
        ops.mesh.select_loose_verts()
        ops.mesh.delete(type = 'VERT')
        ops.mesh.select_all(action = 'SELECT')
        ops.mesh.separate(type = 'LOOSE')
        ops.object.mode_set()
        print("separated") 
        
    def layer(self, n):
        ret = []
        for i in range(0, 20):
            if i == n-1:
                ret.append(True)
            else:
                ret.append(False)
        return ret       
    
    def doParenting(self, context, parentName, nameStart, bbox, backup, largest, obj):
        print("Largest: ", largest)    
        
        parent = None
        if context.active_object == None:
            parent = backup.parent
        else:
            parent = context.active_object.parent
        
        ops.object.add(type = 'EMPTY') 
        context.active_object.game.physics_type = 'STATIC'            
        context.active_object.game.radius = 0.01  
        context.active_object.game.use_ghost = True
              
        context.active_object.name = parentName   
        
        print("PARENT: ", parent)
        context.active_object.parent = parent
        context.active_object.destruction.gridBBox = bbox
  
       # dd.DataStore.backups[context.active_object.name] = backup
        backup.destruction.is_backup_for = context.active_object.name
        
        #get the first backup, need that position
        if parent == None:
           # pos = dd.DataStore.backups["P0_" + nameStart + ".000"].location
            for o in data.objects:
                if o.destruction != None:
                    if o.destruction.is_backup_for == "P_0_" + nameStart + ".000":
                        pos = o.location
                        pos += Vector(o.destruction.tempLoc) #needed for voronoi
                        o.destruction.tempLoc = Vector((0, 0, 0))
            print("EMPTY Pos: ", pos)
            context.active_object.location = pos
        else:
            pos = Vector((0.0, 0.0, 0.0)) 
        oldPar = parent
        
        parent = context.active_object
        parent.destruction.pos = obj.destruction.pos
        parent.destruction.destroyable = True
        parent.destruction.partCount = obj.destruction.partCount
        parent.destruction.wallThickness = obj.destruction.wallThickness
        parent.destruction.pieceGranularity = obj.destruction.pieceGranularity
        parent.destruction.destructionMode = obj.destruction.destructionMode
        parent.destruction.roughness = obj.destruction.roughness
        parent.destruction.crack_type = obj.destruction.crack_type
        
        parent.destruction.gridDim = obj.destruction.gridDim
        parent.destruction.isGround = obj.destruction.isGround
        parent.destruction.destructor = obj.destruction.destructor
        parent.destruction.cubify = obj.destruction.cubify
        parent.destruction.flatten_hierarchy = obj.destruction.flatten_hierarchy
        parent.destruction.backup = backup.name
        
        
        #distribute the object mass to the single pieces, equally for now
        print("Mass: ", backup.game.mass)
        mass = backup.game.mass / backup.destruction.partCount
        backupParent = context.active_object
        context.scene.objects.active = obj
        
        normalList = [p.normal for p in backup.data.polygons]
    #    normals = set(normalList)
         
        if not obj.destruction.flatten_hierarchy:
            parent.layers = self.layer(context.scene.hideLayer)
    
        [self.applyDataSet(context, c, largest, parentName, pos, mass, backup, normalList) for c in context.scene.objects if 
         self.isRelated(c, context, nameStart, oldPar)] 
         
        if (not obj.destruction.flatten_hierarchy) and context.scene.hideLayer != 1:
           # backup.name += "backup"
            backup.parent = backupParent
            if backupParent.name.startswith("P_0_"):
                backup.layers = self.layer(1)
        else:
            backup.use_fake_user = True
          
        #deactivate old compound settings always (not only if flatten hierarchy)
        if parent.parent != None and context.scene.hideLayer == 1:
            self.delCompound(parent.parent)
        
        
        if backup.name not in context.scene.backups:
            prop = context.scene.backups.add()
            prop.name = backup.name
        
        #re-assign compound if parent is fractured     
        if backup.game.use_collision_compound and context.scene.hideLayer != 1:
            self.setCompound(parent.parent)
             
        self.setCompound(parent)
        
        if not obj.destruction.flatten_hierarchy and context.scene.hideLayer != 1:
            backup.game.use_collision_compound = False
            if backup.name.endswith(".000"):
                backup.select = True
                ops.object.origin_set(type = "GEOMETRY_ORIGIN")
                backup.select = False
        
        return parent
    
    def delCompound(self, parent):
        for c in parent.children:
            if c.game.use_collision_compound:
                print("WasCompound", c.name)
                c.destruction.wasCompound = True
                c.game.use_collision_compound = False
            self.delCompound(c)
    
    def setCompound(self, parent):
        loc = Vector((0, 0, 0)) 
        mindist = sys.maxsize
        closest = None
            
        for c in parent.children:
            if c.type == 'MESH' and c.name not in bpy.context.scene.backups:# and not c.name.endswith("backup"):
                dist = (loc - c.location).length
                # print(mindist, dist, c)
                if dist < mindist:
                    mindist = dist
                    closest = c         
                
        #lastChild = parent.children[len(parent.children) - 1]
        if closest != None:
            print("Closest", closest.name)
            closest.game.use_collision_compound = True   
        
    def prepareParenting(self, context, obj):
        
        context.object.destruction.pos = obj.location.to_tuple()
        bbox = obj.bound_box.data.dimensions.to_tuple()
        
        context.scene.objects.active = obj
        
        split = obj.name.split(".")
        parentName = ""
        nameStart = ""
        nameEnd = ""
        
        if len(split) > 1:
            s = ""
            for i in split[:-1]:
                s = s + "." + i
            s = s.lstrip(".")
            nameStart =  s
            nameEnd = split[-1]
        else:
            if not obj.name.startswith("S_"):
                nameStart = "S_" + obj.name
            else:
                nameStart = obj.name
            obj.name = nameStart# + ".000"
            nameEnd = "000"
        
        parentName = "P_0_" + nameStart + "." + nameEnd
   
        #and parent them all to an empty created before -> this is the key
        #P_name = Parent of
        
        children = context.scene.objects
        largest = nameEnd
        level = 0
      
        if obj.parent != None:
            pLevel = obj.parent.name.split("_")[1]
            #temp = pLevel.lstrip("P")
            level = int(pLevel)
            level += 1
            #get child with lowest number, must search for it if its not child[0]
            parentName = "P_" + str(level) + "_" + obj.name
           # nameStart = "S_" + str(level) + "_" + obj.name
            print("Subparenting...", children)
            length = len(obj.parent.children)
            
            #get the largest child index number, hopefully it is the last one and hopefully
            #this scheme will not change in future releases !
            #if obj.destruction.flatten_hierarchy or context.scene.hideLayer == 1:
            largest = obj.parent.children[length - 1].name.split(".")[1]
            #else:
             #   largest = obj.parent.children[length - 2].name.split(".")[1]   #hack, TODO
         
        return parentName, nameStart, largest, bbox    
        
        
    
    def valid(self,context, child):
        return child.name.startswith(context.object.name)
    
    def applyDataSet(self, context, c, nameEnd, parentName, pos, mass, backup, normals):
        print("NAME: ", c.name)
        
        end = 0
        if not c.name.endswith("backup"):
            split = c.name.split(".")
            end = split[1]
        
        if (int(end) > int(nameEnd)) or self.isBeingSplit(c, parentName) and c.parent == None:
            self.assign(c, parentName, pos, mass, backup, context, normals)  
        
    def assign(self, c, parentName, pos, mass, backup, context, normals):
         
        #correct a parenting "error": the parts are moved pos too far
        c.location -= pos
         
        c.parent = data.objects[parentName]
        
    #    if c != backup:
        c.game.physics_type = 'RIGID_BODY'
     #   else:
      #      c.game.physics_type = 'STATIC'
        
        #c.scale = [0.999, 0.999, 0.999]
        
        materialname = backup.destruction.inner_material
       # print("Mat", materialname)
        if materialname != None and materialname != "":
            slots = len(c.material_slots)
            ctx = context.copy()
            ctx["object"] = c
            bpy.ops.object.material_slot_add(ctx)
        
            material = data.materials[materialname]
            c.material_slots[slots].material = material
            
          #  print("Normals", normals)
            facelist = [f for f in c.data.polygons if not self.testNormal(f.normal, normals)]
            for f in facelist:
        #        print("Assigning index", slots)
                f.material_index = slots
        
        #update stale data
        context.scene.objects.active = c
        ops.object.mode_set(mode = 'EDIT')
        ops.object.mode_set(mode = 'OBJECT')
        
        c.game.collision_bounds_type = 'CONVEX_HULL'
        c.game.collision_margin = 0.0 
        c.game.radius = 0.01
        c.game.use_collision_bounds = True
       
        c.select = True
        
       # ops.object.transform_apply(scale = True)  
        c.game.mass = mass 
        
        c.destruction.transmitMode = 'T_SELF'
        c.destruction.destroyable = False
        c.destruction.partCount = 1
        c.destruction.wallThickness = 0.01
        c.destruction.pieceGranularity = 0
        c.destruction.destructionMode = 'DESTROY_F'
        c.destruction.flatten_hierarchy = c.parent.destruction.flatten_hierarchy
        c.layers = c.parent.layers
            
        #if context.active_object.destruction.keep_backup_visible:
        #    c.hide_render = True
        
    
    def isBeingSplit(self, c, parentName):
        if c.name.endswith("backup"):
            return False
        if parentName.split(".")[1] == c.name.split(".")[1]:
            return True
        return False
   
        
    def applyFracture(self, context, objects, parts, roughness, crack_type):
        
        for obj in objects:
            parentName, nameStart, largest, bbox = self.prepareParenting(context, obj)
            backup = self.createBackup(context, obj) 
            
            #fracture the sub objects if cubify is selected
           
            if obj.destruction.cubify:
                self.cubify(context, obj, bbox, parts)
            else:
                fo.fracture_basic(context, [obj], parts, crack_type, roughness)
            
            parent = self.doParenting(context, parentName, nameStart, bbox, backup, largest, obj)
            
            for c in parent.children:
                c.destruction.groundConnectivity = False
                c.destruction.cubify = False
                c.destruction.gridDim = (1,1,1)
                         
        return None
    
    def edgeCount(self, vertex, mesh):
        occurrence = 0
        for key in mesh.edge_keys:
            if vertex == mesh.vertices[key[0]] or vertex == mesh.vertices[key[1]]:
                occurrence += 1
        print("Vertex has ", occurrence, " edges ")        
        return occurrence
        
    def getSize(self, obj):
        areas = [f.area for f in obj.data.faces]
        return sum(areas)
    
    def dictItem(self, dict, key, value):
        dict[key] = value
        
    def applyKnife(self, context, objects, parts, jitter, granularity, cut_type):
        
        for obj in objects:
            parentName, nameStart, largest, bbox = self.prepareParenting(context, obj)
            backup = self.createBackup(context, obj) 
            
            if obj.destruction.cubify:
                self.cubify(context, obj, bbox, parts)
            else:
                self.knife(context, obj, parts, jitter, granularity, cut_type)
              
            parent = self.doParenting(context, parentName, nameStart, bbox, backup, largest, obj)
            
            for c in parent.children:
                c.destruction.groundConnectivity = False
                c.destruction.cubify = False
                c.destruction.gridDim = (1,1,1)
        
        
    def testNormal(self, normal, normals):
        for n in normals:
            dot = round(n.dot(normal), 5)
            prod = round(n.length * normal.length, 5)
            if dot == prod or n == normal:
                #normals point in same direction
                return True
        return False
               
        #get orthogonal projection of Vector between face(need center) and object.location AND
        #normal vector
        #pick the first face (since ALL faces should be consistent by now)
       # if len(ob.data.faces) == 0:
        #    #hmm when getting an invalid object this may occur, so catch it
        #    return False
        
        #find one selected face
        #face = None
        #for f in ob.data.faces:
        #    if f.select:
        #        face = f
        #        break
            
        #if face == None:
        #    return False
        
       # for n in normals:
      #  normal = face.normal
    #    center = face.center
     #   vecCL = center - ob.location
      #  vecProj = vecCL.project(normal)
        
      #  dot = round(normal.dot(vecProj), 2)
    #    length = round(vecProj.length, 2)
        
        #if vecProj and vecCL point to same direction (dot > 0) -> normal points inside, do flip
     #   print("Dot/Length: ", dot , length)
      #  return dot == length 
        
           
    def knife(self, context, ob, parts, jitter, granularity, cut_type):
        
        currentParts = [ob.name]
        
        #print("ob in SCENE: ", ob, ob.name in context.scene)
        context.scene.objects.active = ob
        ops.object.mode_set(mode = 'EDIT')
        #subdivide the object once, say 10 cuts (let the user choose this)
        ops.mesh.subdivide(number_cuts = granularity)
        ops.object.mode_set(mode = 'OBJECT')
        
        zero = Vector((0, 0, 0))
        align = [1, 0, 0, 0]
        matrix = Matrix.Identity(4)
        
        area = None
        region = None
        for a in context.screen.areas:
            if a.type == 'VIEW_3D':
                area = a
                reg = [r for r in area.regions if r.type == 'WINDOW']          
                region = reg[0]
        
        #move parts to center of SCREEN to cut them correctly
        for s in area.spaces:
            if s.type == 'VIEW_3D':
                zero = s.region_3d.view_location
                align = s.region_3d.view_rotation
                matrix = s.region_3d.view_matrix
        
        #for 1 ... parts
        tries = 0
        isHorizontal = False
        names = [ob.name]
        sizes = [self.getSize(ob)]
      #  undoOccurred = False
        
        while (len(currentParts) < parts):
                    
            #give up when always invalid objects result from operation
        #    partFlipped = False
        #    tocutFlipped = False
            if tries > 100:
                break
            
            for o in context.scene.objects:
                o.select = False
                 
            oldnames = [o.name for o in context.scene.objects]
            
            #split by loose parts -> find new names, update oldnames, names and sizes, then proceed as usual
            #pick largest object first
           
            name = names[len(names) - 1] 
            
           # print("Oldnames/names : ", len(oldnames), len(names))
            
            tocut = context.scene.objects[name]
            context.scene.objects.active = tocut
            
            ops.object.mode_set(mode = 'EDIT')
            ops.mesh.select_all(action = 'SELECT')
            ops.mesh.separate(type = 'LOOSE')
            ops.mesh.select_all(action = 'DESELECT')
            ops.object.mode_set(mode = 'OBJECT')
            
            newObj = self.findNew(context, oldnames)
            for obj in newObj:
                oldnames.append(obj.name)
                sizeNew = self.getSize(obj)
                indexNew = bisect.bisect(sizes, sizeNew)
                sizes.insert(indexNew, sizeNew)
                names.insert(indexNew, obj.name)
                
              
            #re-pick the new largest object to subdivide next
            name = names[len(names) - 1] 
            tocut = context.scene.objects[name]
            
           
            tocut.select = True
            ops.object.duplicate()
            tocut.select = False
            backupName = self.findNew(context, oldnames)[0].name
            print("Created Backup: ", backupName)

            backup = context.scene.objects[backupName]
            backup.name = "KnifeBackup"
            context.scene.objects.unlink(backup)
            
            context.scene.objects.active = tocut
            
            rotStart = context.active_object.destruction.rot_start
            rotEnd = context.active_object.destruction.rot_end
             
            parent = context.active_object.parent
            anglex = random.randint(rotStart, rotEnd)
            anglex = math.radians(anglex)
            
            angley = random.randint(rotStart, rotEnd)
            angley = math.radians(angley)
            
            anglez = random.randint(rotStart, rotEnd)
            anglez = math.radians(anglez)
            
           
                
         #   if isHorizontal:
         #        anglex += math.radians(90)
         #       angley += math.radians(90)
         #      anglez += math.radians(90)
            
            
            #pick longest side of bbox
            dims = tocut.bound_box.data.dimensions.to_tuple()
            mx = max(dims)
            index = dims.index(mx)
         #   print(mx, index, dims)    
            
            
            #store old rotation in quaternions and align to view
            tocut.rotation_mode = 'QUATERNION'
            oldquat = Quaternion(tocut.rotation_quaternion)
            tocut.rotation_quaternion = align
            context.scene.update()
          
            tocut.rotation_mode = 'XYZ'
            
            # a bit variation (use lower values...)
            if (index < 2):
                
                euler = align.to_euler()
                euler.rotate_axis('X', anglex)
                euler.rotate_axis('Y', anglex)
                euler.rotate_axis('Z', anglex)
                
                context.active_object.rotation_euler = (euler.x, euler.y, euler.z)
                context.scene.update()
            
            loc = Vector(context.active_object.location)
            context.active_object.location = zero
            context.scene.update()
            
            print("POS", context.active_object.location)
            
            #maybe rotate by 90 degrees to align ?
            
          
           # indexRot = [0,0,0]
            
            if index == 0:
                # x is longest, cut vertical
                isHorizontal = True 
            elif index == 1:
                # y is longest, cut horizontal
                isHorizontal = False    
                
            elif index == 2:
                #z is longest, so rotate by 90 degrees around x, then cut horizontal
                #indexRot = tocut.rotation_euler
                ortho = align.to_euler()
                ortho.rotate_axis('X', math.radians(90))
            #    axis = ortho.to_quaternion().axis
            #    ops.transform.rotate(value = [math.radians(90)], axis = axis)
            
                 #vary a bit
                ortho.rotate_axis('X', anglex)
                ortho.rotate_axis('Y', angley)
                ortho.rotate_axis('Z', anglez)
                
                context.active_object.rotation_euler = (ortho.x, ortho.y, ortho.z)
                context.scene.update()
                isHorizontal = False
            
            #context.scene.objects.active = tocut
            #make a random OperatorMousePath Collection to define cut path, the higher the jitter
            #the more deviation from path
            #opmousepath is in screen coordinates, assume 0.0 -> 1.0 since 0.5 centers it ?
            #[{"name":"", "loc":(x,y), "time":0},{...}, ...]
            
            width = region.width
            height = region.height
            
            lineStart = context.active_object.destruction.line_start
            lineEnd = context.active_object.destruction.line_end
            
            path = []
            if cut_type == 'LINEAR':
               # isHorizontal = not isHorizontal
                path = self.linearPath(context, tocut, jitter, width, height, isHorizontal, lineStart, lineEnd)
            elif cut_type == 'ROUND':
                path = self.spheroidPath(jitter, width, height, lineStart, lineEnd)
            
          #  print("PATH: ", path, tocut.location, tocut.rotation_euler)    
            #apply the cut, exact cut
            ops.object.mode_set(mode = 'EDIT')
            ops.mesh.select_all(action = 'SELECT')
            
            ctx = context.copy()
            ctx["area"] = area
            ctx["region"] = region
            ops.mesh.knife_cut(ctx, type = 'EXACT', path = path, region_width = region.width, region_height = region.height,
                               perspective_matrix = matrix)
            
            part = self.handleKnife(context, tocut, backup, names, oldquat, loc, oldnames, tries)
            
            #use fallback method if no patch available
            # create cutters
            
            
            if part == None:
                tries += 1
                continue
            
            obj = context.active_object
            
            if len(obj.data.vertices) == 0 or len(tocut.data.vertices) == 0:
                print("Undo (no vertices)...")
                context.scene.objects.unlink(tocut)
                context.scene.objects.unlink(obj)
                backup.name = tocut.name
                context.scene.objects.link(backup)
                
                tries += 1
                continue
            
            manifold1 = min(mesh_utils.edge_face_count(obj.data))
            manifold2 = min(mesh_utils.edge_face_count(tocut.data))
            
           # print(manifold1, manifold2)
            manifold = min(manifold1, manifold2)
            
            #manifold = 2
            if manifold < 2:
                print("Undo (non-manifold)...", tocut.name, obj.name)
                
                
                context.scene.objects.unlink(tocut)
                context.scene.objects.unlink(obj)
          
                #backup.name = tocut.name
                context.scene.objects.link(backup)
                backup.name = tocut.name #doesnt really work... Blender renames it automatically
            
                #so update the names array
                print("Re-linked: ", backup.name, tocut.name)
                del names[len(names) - 1]
                names.append(backup.name)
                #if tocut.name in oldnames:
                #    oldnames.remove(tocut.name)
                #if backup.name in oldnames:
                #    oldnames.remove(backup.name)
                    
                #undoOccurred = True
                tries += 1
                #undoOccurred = True
                continue
                      
            currentParts.append(part)
            
            #context.object seems to disappear so store parent in active object
            context.active_object.parent = parent
            tries = 0
            print("Split :", tocut.name, part)
            
            # update size/name arrays
            # remove the last one because this was chosen to be split(its the biggest one)
            del sizes[len(sizes) - 1]
            del names[len(names) - 1]
            
            sizeTocut = self.getSize(tocut)
            sizePart = self.getSize(context.scene.objects[part])
            
            indexTocut = bisect.bisect(sizes, sizeTocut)
            sizes.insert(indexTocut, sizeTocut)
            names.insert(indexTocut, tocut.name)
            
            indexPart = bisect.bisect(sizes, sizePart)
            sizes.insert(indexPart, sizePart)
            names.insert(indexPart, part)
                           
           
    def handleKnife(self, context, tocut, backup, names, oldquat, loc, oldnames, tries):
            ops.object.mode_set(mode = 'OBJECT')
            
            #restore rotations 
        #    if index == 2:
        #       context.active_object.rotation_euler = indexRot
        #        context.scene.update()
          
            context.active_object.rotation_mode = 'QUATERNION'
            context.active_object.rotation_quaternion = oldquat
            
         #   context.active_object.rotation_euler = (0, 0, 0)
            context.scene.update()
            context.active_object.rotation_mode = 'XYZ'
     
            context.active_object.location = loc
            context.scene.update()
          
            
            ops.object.mode_set(mode = 'EDIT')
            ops.mesh.loop_to_region()
            
            #separate object by selection
          #  print("BEFORE", len(context.scene.objects))
            ops.mesh.separate(type = 'SELECTED')
          #  print("AFTER", len(context.scene.objects))
            
            newObject = self.findNew(context, oldnames)
            if len(newObject) > 0:
                part = newObject[0].name
            else:
                part = None
             
            ops.mesh.select_all(action = 'SELECT')
            ops.mesh.region_to_loop()
            ops.mesh.fill()
                
            ops.object.mode_set(mode = 'OBJECT')
            tocut.select = True
            ops.object.origin_set(type = 'ORIGIN_GEOMETRY')
            tocut.select = False
            
            ops.object.mode_set(mode = 'EDIT')
           # ops.mesh.select_all(action = 'DESELECT')
        #    ops.mesh.select_all(action = 'SELECT')
            ops.mesh.normals_make_consistent(inside = False)
            
#            if self.testNormalInside(tocut):
#                ops.mesh.normals_make_consistent(inside = False)
#                tocutFlipped = True
            
            ops.object.mode_set(mode = 'OBJECT')
            
             #missed the object, retry with different values until success   
            if part == None:
                print("Undo (naming error)...")
               
                context.scene.objects.unlink(tocut)
                context.scene.objects.link(backup)
                backup.name = tocut.name #doesnt really work... Blender renames it automatically
            
                #so update the names array
                print("Re-linked: ", backup.name, tocut.name, oldnames)
                del names[len(names) - 1]
                names.append(backup.name)
                if tocut.name in oldnames:
                    oldnames.remove(tocut.name)
                if backup.name in oldnames:
                    oldnames.remove(backup.name)
                
                tries += 1
                return None
            
      
            context.scene.objects.active = context.scene.objects[part]
            ops.object.mode_set(mode = 'EDIT')
            ops.mesh.select_all(action = 'SELECT')
            ops.mesh.region_to_loop()
            ops.mesh.fill()
                    
            ops.object.mode_set(mode = 'OBJECT')
            context.active_object.select = True
            ops.object.origin_set(type = 'ORIGIN_GEOMETRY')
            context.active_object.select = False
            
            ops.object.mode_set(mode = 'EDIT')
            #ops.mesh.select_all(action = 'DESELECT')
            #ops.mesh.select_all(action = 'SELECT')
            ops.mesh.normals_make_consistent(inside = False)
            
            #if self.testNormalInside(context.active_object):
            #   ops.mesh.normals_make_consistent(inside = False)
            #   partFlipped = True
            ops.object.mode_set(mode = 'OBJECT')
            
            return part
     
    def handleKnifeBoolean(self, context, tocut, backup, names, oldquat, loc, oldnames):
        pass
        
        
            
    def linearPath(self, context, tocut, jitter, width, height, isHorizontal, lineStart, lineEnd):
        startx = 0;
        starty = 0
        endx = width
        endy = height
        
        
        steps = 100
        if jitter > 0.01:
           steps = random.randint(100, 200)
        
        if isHorizontal:
            startPercentage = round((lineStart / 100 * width), 0)
            endPercentage = round((lineEnd / 100 * width), 0)
            startx = random.randint(startPercentage, endPercentage)
            starty = 0
            endx = width - startx
            endy = height
            
            #create cutters which are aligned like the path would be, for fallback method
            #size them in width/height and move to center (-width/height / 2)
          #  ops.mesh.primitive_cube_add(view_align=True, location = tocut.location.to_tuple(), 
        #                                rotation = tocut.rotation_euler.to_tuple())
                                        
         #   cutter = context.active_object
        #    cutter.dimensions = tocut.bound_box.data.dimensions   
        
        else:
            startPercentage = round((lineStart / 100 * height), 0)
            endPercentage = round((lineEnd / 100 * height), 0)
            startx = 0
            starty = random.randint(startPercentage, endPercentage)
            endx = width
            endy = height - starty
        
            
        deltaX = (endx - startx) / steps
        deltaY = (endy - starty) / steps
        
        delta = math.sqrt(deltaX * deltaX + deltaY * deltaY)
        sine = deltaX / delta
        cosine = deltaY / delta
        if isHorizontal:
             sine = deltaY / delta
             cosine = deltaX / delta
        
        path = [] 
        path.append(self.entry(startx, starty))
        
        for i in range(1, steps + 1):
            x = startx + i * deltaX
            y = starty + i * deltaY
            
            if jitter > 0.01:
                jit = random.uniform(-jitter, jitter) 
                if isHorizontal:
                    x += (cosine * jit * width / 100)
                    y -= (sine * jit * height / 100)
                else:
                    x -= (sine * jit * width / 100)
                    y += (cosine * jit * height / 100)
                    
            path.append(self.entry(x,y))
  
        return path        
    
    def spheroidPath(self, jitter, width, height, lineStart, lineEnd):
        midx = random.randint(0, width)
        midy = random.randint(0, height)
       # maxrad = height / 4
    #    if height > width:
     #       maxrad = width / 4
        startPercentage = round((lineStart / 100 * width), 0)
        endPercentage = round((lineEnd / 100 * width), 0)
        
        radius = random.uniform(startPercentage, endPercentage)
        steps = random.randint(100, 200)
        
        deltaAngle = 360 / steps
        
        angle = 0
        path = []
        for i in range(0, steps):
            x = midx + math.cos(math.radians(angle)) * radius
            y = midy + math.sin(math.radians(angle)) * radius
            
            #if jitter > 0:
            #   x += random.uniform(-jitter, jitter)
            #   y += random.uniform(-jitter, jitter)
            
            path.append(self.entry(x,y))  
            angle += deltaAngle  
        
        return path  
           
    def entry(self, x, y):
        return {"name":"", "loc":(x, y), "time":0}
    
    def findNew(self, context, oldnames):
        ret = []
        for o in context.scene.objects:
            if o.name not in oldnames:
                ret.append(o)
        print("found: ", ret)
        return ret
            
    
    def isRelated(self, c, context, nameStart, parent):
        
        split = c.name.split(".")
        nameEnd = split[-1]
        objname = ""
        for s in split[:-1]:
            objname = objname + "." + s
        objname = objname.lstrip(".")
      #  print("OBJ", objname, nameStart)
        print("Related: ", c.name, c.parent, parent)
        return (objname == nameStart) and c.parent == parent
              
    def endStr(self, nr):
        if nr < 10:
            return "00" + str(nr)
        if nr < 100:
            return "0" + str(nr)
        return str(nr)
        
    def cubify(self, context, object, bbox, parts):
        #create a cube with dim of cell size, (rotate/position it accordingly)
        #intersect with pos of cells[0], go through all cells, set cube to pos, intersect again
        #repeat always with original object
        
        grid = dd.Grid(object.destruction.cubifyDim, 
                       object.destruction.pos,
                       bbox, 
                       [], 
                       object.destruction.grounds)
            
        ops.mesh.primitive_cube_add()
        cutter = context.active_object
        cutter.name = "Cutter"
        cutter.select = False
     
        cubes = []
        for cell in grid.cells.values():
            ob = self.cubifyCell(cell,cutter, context)
            cubes.append(ob)
           
       
        context.scene.objects.unlink(cutter)
        
        if parts > 1: 
            if object.destruction.destructionMode == 'DESTROY_F':
                crack_type = object.destruction.crack_type
                roughness = object.destruction.roughness
                context.scene.objects.unlink(object) 
                
                fo.fracture_basic(context, cubes, parts, crack_type, roughness)
                
            elif object.destruction.destructionMode == 'DESTROY_K':
                jitter = object.destruction.jitter
                granularity = object.destruction.pieceGranularity
                cut_type = object.destruction.cut_type 
                context.scene.objects.unlink(object) 
                 
                for cube in cubes:
                    self.knife(context, cube, parts, jitter, granularity, cut_type)
            
            elif object.destruction.destructionMode == 'DESTROY_V' or \
                 object.destruction.destructionMode == 'DESTROY_VB':
                 volume = context.object.destruction.voro_volume
                 wall = context.object.destruction.wall
                 context.scene.objects.unlink(object)
                 
                 for cube in cubes:
                     #ops.object.transform_apply(scale=True, location=True)
                     voronoi.voronoiCube(context, cube, parts, volume, wall)
            
            else:
                granularity = object.destruction.pieceGranularity
                thickness = object.destruction.wallThickness
                
                mode = object.destruction.destructionMode
                modes = object.destruction.destModes
                
                massive = False
                pairwise = False
                
                if mode == modes[2][0]:
                    massive = True
                    pairwise = True
                    
                if mode == modes[3][0]:
                    massive = True
                
                context.scene.objects.unlink(object)
                
                for cube in cubes:
                    self.explo(context, cube, parts, granularity, thickness, massive, pairwise)
                
        else:
             context.scene.objects.unlink(context.object)   
              
    def cubifyCell(self, cell, cutter, context):
        context.object.select = True #maybe link it before...
        context.scene.objects.active = context.object
        
        ops.object.duplicate()
        context.object.select = False
        ob = context.active_object
        print(ob, context.selected_objects)
        
       # print(cell, cell.center)
        cutter.location = Vector(cell.center)
        cutter.dimensions = Vector(cell.dim) * 1.01
        context.scene.update()
        
        bool = ob.modifiers.new("Boolean", 'BOOLEAN')
        bool.object = cutter
        bool.operation = 'INTERSECT'
        
       # copy = context.copy()
       # copy["object"] = ob
       # ops.object.modifier_apply(copy)
        mesh = ob.to_mesh(context.scene, 
                          apply_modifiers=True, 
                          settings='PREVIEW')
        print(mesh)                  
        old_mesh = ob.data
        ob.data = None
        old_mesh.user_clear()
        
        if (old_mesh.users == 0):
            bpy.data.meshes.remove(old_mesh)  
            
        ob.data = mesh 
        ob.select = False
        ob.modifiers.remove(bool)
        
        ops.object.mode_set(mode = 'EDIT')  
        ops.mesh.select_all(action = 'SELECT')
        ops.mesh.remove_doubles(mergedist = 0.01)
        ops.object.mode_set(mode = 'OBJECT') 
        
        ob.select = True
        ops.object.origin_set(type = 'ORIGIN_GEOMETRY') 
        ob.select = False
        
        context.scene.objects.active = context.object 
        
        return ob
                        
                    
def updateGrid(self, context):
    return None

def updateDestructionMode(self, context):
    return None

def updatePartCount(self, context):
    return None

def updateWallThickness(self, context):
    return None

def updatePieceGranularity(self, context):
    return None

def updateIsGround(context):
    #updateValidGrounds(context.object) 
    for c in context.object.children:
        c.destruction.isGround = context.object.destruction.isGround      
    return None


def updateGroundConnectivity(self, context):
    return None

def updateDestructor(context):
    
    for c in context.object.children:
        c.destruction.destructor = context.object.destruction.destructor
        if c.destruction.destructor:
            for p in context.object.destruction.destructorTargets:
                prop = c.destruction.destructorTargets.add()
                prop.name = p.name
        else:
            for p in context.object.destruction.destructorTargets:
                index = 0
                found = False
                for prop in c.destruction.destructorTargets:
                    if p.name == prop.name:
                        found = True    
                        break
                    index += 1
                    
                if found:
                    c.destruction.destructorTargets.remove(index)        
                    
    return None


#def updateTransmitMode(self, context):
#   # print("TRANSMITMODE:", context.object.destruction.transmitMode)
#    return None 

def updateTransmitMode(self, context):
    return None 

def updateDestroyable(self, context):
   # updateValidTargets(context.object)
    return None 

#disable decorator when persistence is not available
def unchanged(func):
    return func

pers = unchanged
if imported:
    pers = persistent

@pers
def updateValidTargets(object):
    #print("Current Object is: ", object)
    
    #for index in range(0, len(bpy.context.scene.validTargets)):
        #print("Removing :", index)
    #    bpy.context.scene.validTargets.remove(index)
    if object.destruction.destroyable:
        if object.name not in bpy.context.scene.validTargets:
            prop = bpy.context.scene.validTargets.add()
            prop.name = object.name
    else:
        #print("Not:", object.name)
        if object.name in bpy.context.scene.validTargets:
            index = bpy.context.scene.validTargets.index(object.name)
            bpy.context.scene.validTargets.remove(index) 
         #   print("Removing valid:", object.name)
            
        for o in bpy.context.scene.objects:
            if o.destruction.destructor and object.name in o.destruction.destructorTargets:
                index = 0
                for ob in o.destruction.destructorTargets:
                    if ob.name == object.name:
                        break
                    index += 1
          #      print("Removing:", object.name)
                o.destruction.destructorTargets.remove(index)
    
   # for o in bpy.context.scene.objects:
    #    if o.destruction.destroyable and o != object and \
    #    o.name not in object.destruction.destructorTargets and \
     #   o.name not in bpy.context.scene.validTargets:
           #print("Adding :", o.name)
      #     prop = bpy.context.scene.validTargets.add()
    #       prop.name = o.name
           
    return None 

@pers
def updateValidGrounds(object):
    #print("Current Object is: ", object)
   
   # for index in range(0, len(bpy.context.scene.validGrounds)):
    #    bpy.context.scene.validGrounds.remove(index)
    
    #for o in bpy.context.scene.objects:
    #    if o.destruction.isGround and o != object and \
    #    o.name not in object.destruction.grounds and \
    #    o.name not in bpy.context.scene.validGrounds:
    #       prop = bpy.context.scene.validGrounds.add()
    #       prop.name = o.name
    
    if object.destruction.isGround:
        if object.name not in bpy.context.scene.validGrounds:
            prop = bpy.context.scene.validTargets.add()
            prop.name = object.name
    else:
       # print("Not:", object.name)
        if object.name in bpy.context.scene.validGrounds:
            index = bpy.context.scene.validGrounds.index(object.name)
            bpy.context.scene.validTargets.remove(index) 
        #    print("Removing valid:", object.name)
            
        for o in bpy.context.scene.objects:
            if object.name in o.destruction.grounds:
                #index = o.destruction.grounds.index(object.name)
                index = 0
                for ob in o.destruction.grounds:
                    if ob.name == object.name:
                        break
                    index += 1
             
         #       print("Removing:", object.name, index)
                o.destruction.grounds.remove(index)
           
    return None

class DestructionContext(types.PropertyGroup):
    
    def getVolumes():
        ret = []
        for o in bpy.context.scene.objects:
            if o.type == 'MESH' and o != bpy.context.scene.objects.active:
                ret.append((o.name, o.name, o.name))
        return ret
    
    destModes = [('DESTROY_F', 'Boolean Fracture', 'Destroy this object using boolean fracturing', 0 ), 
             ('DESTROY_E_H', 'Explosion Modifier', 
              'Destroy this object using the explosion modifier, forming a hollow shape', 1),
             #('DESTROY_E_M', 'Explosion Modifier (Massive)', 
             #  'Destroy this object using the explosion modifier, forming a massive shape', 2),
             #('DESTROY_E_P', 'Explosion Modifier (Small Pieces)', 
             #  'Destroy this object using the explosion modifier, forming small pieces', 3),
             ('DESTROY_K', 'Knife Tool', 'Destroy this object using the knife tool', 2),
             ('DESTROY_V', 'Voronoi Fracture', 'Destroy this object using voronoi decomposition', 3),
             ('DESTROY_VB', 'Voronoi + Boolean', 'Destroy this object simple voronoi and a boolean modifier', 4)] 
             
    
    transModes = [('T_SELF', 'This Object', 'Apply settings to this object only', 0), 
             ('T_SELECTED', 'Selected', 'Apply settings to all selected objects as well', 1)]
             #('T_CHILDREN', 'Selected + Direct Children', 'Apply settings to direct children of selected objects as well', 2),
            # ('T_ALL_CHILDREN', 'Selected + All Descendants', 'Apply settings to all descendants of selected objects as well', 3)]
             #('T_LAYERS', 'Active Layers', 'Apply settings to all objects on active layers as well', 4), 
             #('T_ALL', 'All Objects', 'Apply settings to all objects as well', 5) ]
    
    destroyable = props.BoolProperty(name = "destroyable",
                         description = "This object can be destroyed, according to parent relations", 
                         update = updateDestroyable)
    
    partCount = props.IntProperty(name = "partCount", default = 10, min = 1, max = 999, update = updatePartCount)
    destructionMode = props.EnumProperty(items = destModes, update = updateDestructionMode)
    destructor = props.BoolProperty(name = "destructor", 
                        description = "This object can trigger destruction")#, update = updateDestructor)
    isGround = props.BoolProperty(name = "isGround", 
     description = "This object serves as a hard point, objects not connected to it will be destroyed")
     #update = updateIsGround)
     
    groundConnectivity = props.BoolProperty(name = "groundConnectivity", 
    description = "Determines whether connectivity of parts of this object is calculated, so only unconnected parts collapse according to their parent relations", update = updateGroundConnectivity)
    gridDim = props.IntVectorProperty(name = "grid", default = (1, 1, 1), min = 1, max = 100, 
                                          subtype ='XYZ', update = updateGrid )
                                          
    cubifyDim = props.IntVectorProperty(name = "cubifyDim", default = (1, 1, 1), min = 1, max = 100, 
                                          subtype ='XYZ' )
    
    gridBBox = props.FloatVectorProperty(name = "gridbbox", default = (0, 0, 0))
    destructorTargets = props.CollectionProperty(type = types.PropertyGroup, name = "destructorTargets")
    grounds = props.CollectionProperty(type = types.PropertyGroup, name = "grounds")
    transmitMode = props.EnumProperty(items = transModes, name = "Transmit Mode", update = updateTransmitMode)
    active_target = props.IntProperty(name = "active_target", default = 0)
    active_ground = props.IntProperty(name = "active_ground", default = 0)
 
    groundSelector = props.StringProperty(name = "groundSelector")
    targetSelector = props.StringProperty(name = "targetSelector")

    wallThickness = props.FloatProperty(name = "wallThickness", default = 0.01, min = 0, max = 10,
                                      update = updateWallThickness)
    pieceGranularity = props.IntProperty(name = "pieceGranularity", default = 4, min = 0, max = 100, 
                                         update = updatePieceGranularity)
    applyDone = props.BoolProperty(name = "applyDone", default = False)
    previewDone = props.BoolProperty(name = "previewDone", default = False)
    
   
    pos = props.FloatVectorProperty(name = "pos" , default = (0, 0, 0))
 #   currentKnifePath = props.CollectionProperty(type = types.OperatorMousePath, name = "currentKnifePath")
    rot_start = props.IntProperty(name = "rot_start", default = -30, min = -90, max = 90)
    rot_end = props.IntProperty(name = "rot_end", default = 30, min = -90, max = 90)
    
    line_start = props.IntProperty(name = "line_start", default = 0, min = 0, max = 100)
    line_end = props.IntProperty(name = "line_end", default = 100, min = 0, max = 100)
    
    hierarchy_depth = props.IntProperty(name = "hierarchy_depth", default = 1, min = 1)
    flatten_hierarchy = props.BoolProperty(name = "flatten_hierarchy", default = True)
    
    voro_volume = props.StringProperty(name="volumeSelector")
    is_backup_for = props.StringProperty(name = "is_backup_for")
    wall = props.BoolProperty(name = "wall", default = True)
    tempLoc = props.FloatVectorProperty(name = "tempLoc", default = (0, 0, 0))
    custom_ball = props.StringProperty(name="custom_ball")
    voro_exact_shape = props.BoolProperty(name = "voro_exact_shape")
    voro_path = props.StringProperty(name="voro_path", default = "test.out")
   # keep_backup_visible = props.BoolProperty(name = "keep_backup_visible")
    inner_material = props.StringProperty(name = "inner_material")
    remesh_depth = props.IntProperty(name="remesh_depth", default = 5, min = 0, max = 10)
    wasCompound = props.BoolProperty(name="wasCompound", default = False)
    children = props.CollectionProperty(type = types.PropertyGroup, name = "children")
    backup = props.StringProperty(name = "backup")
    
    # From pildanovak, fracture script
    crack_type = props.EnumProperty(name='Crack type',
        items=(
            ('FLAT', 'Flat', 'a'),
            ('FLAT_ROUGH', 'Flat rough', 'a'),
            ('SPHERE', 'Spherical', 'a'),
            ('SPHERE_ROUGH', 'Spherical rough', 'a')),
        description='Look of the fracture surface',
        default='FLAT')

    roughness = props.FloatProperty(name="Roughness",
        description="Roughness of the fracture surface",
        min=0.0,
        max=3.0,
        default=0.5)
   # End from        

    grid = None
    jitter = props.FloatProperty(name = "jitter", default = 0.0, min = 0.0, max = 100.0) 
    
    cubify = props.BoolProperty(name = "cubify")
 #   subgridDim = props.IntVectorProperty(name = "subgridDim", default = (1, 1, 1), min = 1, max = 100, 
  #                                        subtype ='XYZ')
  #  cascadeGround = props.BoolProperty(name = "cascadeGround")
    cut_type = props.EnumProperty(name = 'Cut type', 
                items = (
                        ('LINEAR', 'Linear', 'a'),
                        ('ROUND', 'Round', 'a')),
                default = 'LINEAR') 
                
            
    
def initialize():
    Object.destruction = props.PointerProperty(type = DestructionContext, name = "DestructionContext")
    Scene.player = props.BoolProperty(name = "player")
    Scene.converted = props.BoolProperty(name = "converted")
 #   Scene.validTargets = props.CollectionProperty(name = "validTargets", type = types.PropertyGroup)
#    Scene.validGrounds = props.CollectionProperty(name = "validGrounds", type = types.PropertyGroup)
 #   Scene.validVolumes = props.CollectionProperty(name = "validVolumes", type = types.PropertyGroup)
    Scene.hideLayer = props.IntProperty(name = "hideLayer", min = 1, max = 20, default = 1)
    Scene.backups = props.CollectionProperty(name = "backups", type = types.PropertyGroup)
    dd.DataStore.proc = Processor()  
  
    #if hasattr(bpy.app.handlers, "object_activation" ) != 0:
        #bpy.app.handlers.object_activation.append(updateValidTargets)
        #bpy.app.handlers.object_activation.append(updateValidGrounds)
  
def uninitialize():
    del Object.destruction
    
    #if hasattr(bpy.app.handlers, "object_activation" ) != 0:
        #bpy.app.handlers.object_activation.remove(updateValidTargets)
        #bpy.app.handlers.object_activation.remove(updateValidGrounds)
       
    