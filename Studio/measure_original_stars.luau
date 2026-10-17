-- Run in Studio's Command Bar after placing the two measurement Attachments.
-- This reads positions only. It does not alter the original accessory.
-- 1. Name the fitted test mannequin CelestialFitRig.
-- 2. Equip the original Diwali Sparkler Headband on that mannequin.
-- 3. Add two temporary Attachments inside its Handle, place at the actual
--    geometric centers of its original stars, and name them exactly:
--    CelestialTarget_LEFT and CelestialTarget_RIGHT.
-- LEFT = negative X in the HatAttachment coordinate frame.
local rig = workspace:FindFirstChild("CelestialFitRig")
assert(rig, "Name your test mannequin CelestialFitRig")
local head = rig:FindFirstChild("Head")
local hat = head and head:FindFirstChild("HatAttachment")
assert(hat and hat:IsA("Attachment"), "Head.HatAttachment is required")
local config = {}
for _, side in {"LEFT", "RIGHT"} do
    local guide = rig:FindFirstChild("CelestialTarget_" .. side, true)
    assert(guide and guide:IsA("Attachment"), "Missing original-star measurement Attachment: " .. side)
    local p = hat.WorldCFrame:PointToObjectSpace(guide.WorldPosition)
    -- Export axis mapping: Roblox (x,y,z) = Blender (x,z,-y).
    config[side .. "_STAR_TARGET"] = {p.X, -p.Z, p.Y}
end
print("Merge these measured targets into fit_parameters.json:")
print(game:GetService("HttpService"):JSONEncode(config))
