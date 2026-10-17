-- Optional Studio Command Bar helper. NOT an in-game Script inside Accessory.
-- Select the single imported MeshPart. The dimensions/center below are emitted
-- by create_celestial_horns.py; regenerate this file's numbers from manifest
-- if changing fit_parameters. AFT remains the recommended creation workflow.
local Selection = game:GetService("Selection")
local mesh = Selection:Get()[1]
assert(mesh and mesh:IsA("MeshPart"), "Select the imported Celestial_Horns_Handle MeshPart")
local rig = workspace:FindFirstChild("CelestialFitRig")
assert(rig and rig:FindFirstChild("Head"), "CelestialFitRig.Head is required")
local headHat = rig.Head:FindFirstChild("HatAttachment")
assert(headHat and headHat:IsA("Attachment"), "Head.HatAttachment is required")
-- SIZE_AND_CENTER_FROM_MANIFEST -- replaced by Tools/prepare_delivery.py
local targetSize = Vector3.new(2.416188002, 1.659999967, 0.769493222)
local geometryCenter = Vector3.new(0.000000000, 0.699999988, -0.028515190)
mesh.Size = targetSize
mesh.CFrame = headHat.WorldCFrame * CFrame.new(geometryCenter)
mesh.Material = Enum.Material.Plastic
mesh.Color = Color3.new(1, 1, 1)
mesh.Transparency = 0
mesh.CanCollide = false
mesh.Massless = true
mesh.Anchored = true -- unanchor during AFT conversion / equip test
local surface = mesh:FindFirstChildOfClass("SurfaceAppearance") or Instance.new("SurfaceAppearance")
surface.Name = "Celestial_PBR"
surface.Parent = mesh
-- Upload the PNGs and assign ColorMap, MetalnessMap, RoughnessMap, NormalMap,
-- and EmissiveMaskContent in Properties. EmissiveMaskContent is PluginSecurity
-- in the engine API, so assign it in Studio UI rather than a runtime Script.
surface.EmissiveStrength = 1.4
surface.EmissiveTint = Color3.new(1, 1, 1)
print("Dimensions/placement applied. Assign texture assets, then use AFT > Rigid > Hat > Classic.")
