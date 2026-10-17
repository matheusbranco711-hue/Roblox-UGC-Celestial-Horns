-- Studio Command Bar; actual final verification requires BOTH equipped items.
-- Place CelestialAddon_LEFT and CelestialAddon_RIGHT temporary Attachments
-- at the new stars' geometric centers on the imported addon Handle.
-- Keep CelestialTarget_LEFT/RIGHT on the original Handle from measurement.
-- This reports measured center errors in studs; it does not invent a passing
-- publication tolerance. Delete all four measurement Attachments before AFT
-- final creation / publishing, leaving only the actual HatAttachment.
local rig = workspace:FindFirstChild("CelestialFitRig")
assert(rig, "CelestialFitRig is required")
for _, side in {"LEFT", "RIGHT"} do
    local original = rig:FindFirstChild("CelestialTarget_" .. side, true)
    local addon = rig:FindFirstChild("CelestialAddon_" .. side, true)
    assert(original and original:IsA("Attachment"), "Missing original guide: " .. side)
    assert(addon and addon:IsA("Attachment"), "Missing addon guide: " .. side)
    local delta = addon.WorldPosition - original.WorldPosition
    print(string.format("%s: center error %.8f studs; world delta (%.8f, %.8f, %.8f)",
        side, delta.Magnitude, delta.X, delta.Y, delta.Z))
end
print("Also inspect staff coverage, original fireworks, hair clipping and Hat bounds in AFT.")
