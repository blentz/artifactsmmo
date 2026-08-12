import math

MAXHP = 535
THR = 3 / 4 * 535
FIGHT = 30.0
REQ = 4400


def rate(dmg, award):
    hp = MAXHP
    fights = 0
    acc = 0
    while True:
        hp -= dmg
        fights += 1
        acc += dmg
        if hp < THR:
            break
    secs = math.ceil(acc / MAXHP * 100)
    fe = secs / FIGHT
    loop = 1 + fe / fights
    return award / loop, fights, acc, secs, loop


print("A ogre(134):", rate(134, 63))
print("B ogre(133):", rate(133, 63))
skel = 34.0
rA = rate(134, 63)[0]
bestA = max(skel, rA)
print("A pick", "skeleton" if skel > rA else "ogre", REQ / bestA, math.ceil(REQ / bestA))
rB = rate(133, 63)[0]
costB = REQ / rB + 0.2
print("B pick", "ogre" if rB > skel else "skeleton", costB, math.ceil(costB))
