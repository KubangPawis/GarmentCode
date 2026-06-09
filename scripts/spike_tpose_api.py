"""Headless probe: confirm rig add + bone reads + the shoulder rotation work in
Blender, and that the measured droop goes ~45deg -> ~0deg. Run via
scripts/run_blender.sh scripts/spike_tpose_api.py"""
import sys


def _repo():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--repo" in argv:
        sys.path.insert(0, argv[argv.index("--repo") + 1])


def main():
    _repo()
    from mpfb_tpose import human as humanmod, rig as rigmod, geometry
    H, E, R = rigmod.services()
    basemesh = humanmod.create(H, humanmod.macro_dict(gender=0.5))
    arm = rigmod.add_game_engine_rig(basemesh, H)
    mod = [m.name for m in basemesh.modifiers if m.type == "ARMATURE"]
    print("SPIKE armature_modifier:", mod)
    for side, (upper, hand) in rigmod.ARM.items():
        sh = R.find_pose_bone_head_world_location(upper, arm)
        wr = R.find_pose_bone_head_world_location(hand, arm)
        print("SPIKE %s pre droop=%.1f deg  shoulder=%s wrist=%s"
              % (side, geometry.droop_from_horizontal_deg(sh, wr),
                 tuple(round(v, 3) for v in sh), tuple(round(v, 3) for v in wr)))
    applied = rigmod.measure_and_rotate_shoulders(arm, R)
    for side, (upper, hand) in rigmod.ARM.items():
        sh = R.find_pose_bone_head_world_location(upper, arm)
        wr = R.find_pose_bone_head_world_location(hand, arm)
        print("SPIKE %s post droop=%.1f deg (applied %.1f deg)"
              % (side, geometry.droop_from_horizontal_deg(sh, wr),
                 __import__("math").degrees(applied[side])))
    print("SPIKE_DONE")


if __name__ == "__main__":
    main()
