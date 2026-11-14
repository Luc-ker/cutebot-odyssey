# Map icons (T88)

One SVG per `icon` value in `shared/roles.json`, plus `unknown`, `robot` and `giant_hand`.

- 64×64 `viewBox`, simple flat shapes in a storybook style, with a soft ground shadow.
- The main fill is `currentColor`. An `<img>` can't inherit a colour, so the map layers fetch the SVG text,
  replace `currentColor` with the world's palette colour, and draw the result. Outlines and details are a fixed
  dark brown (`#2b1d0e`) so the icons stay readable on any terrain.
- Every icon is self-made for this project. No third-party artwork is included.
- `icons.test.js` (run with `node --test web/map/icons/icons.test.js`) fails if a role's icon is missing.

| File | Roles | Source |
|---|---|---|
| `ash_field.svg` | ash_field | self-made |
| `asteroid.svg` | asteroid | self-made |
| `beacon.svg` | beacon | self-made |
| `boat.svg` | boat | self-made |
| `bridge.svg` | bridge | self-made |
| `camp.svg` | camp | self-made |
| `castle.svg` | castle | self-made |
| `catacombs.svg` | catacombs | self-made |
| `cliff.svg` | cliff | self-made |
| `crystal.svg` | crystal | self-made |
| `den.svg` | den | self-made |
| `docking_tower.svg` | docking_tower | self-made |
| `dragon.svg` | dragon | self-made |
| `drone_swarm.svg` | drone_swarm | self-made |
| `engine_room.svg` | engine_room | self-made |
| `forest.svg` | forest | self-made |
| `fortress.svg` | fortress | self-made |
| `giant.svg` | giant | self-made |
| `glacier.svg` | glacier | self-made |
| `grove.svg` | grove | self-made |
| `harbour.svg` | harbour | self-made |
| `ice_palace.svg` | ice_palace | self-made |
| `island.svg` | island | self-made |
| `jaguar.svg` | jaguar | self-made |
| `jungle_patch.svg` | jungle_patch | self-made |
| `lava_beast.svg` | lava_beast | self-made |
| `lava_cave.svg` | lava_cave | self-made |
| `lighthouse.svg` | lighthouse | self-made |
| `market.svg` | market | self-made |
| `mountain.svg` | mountain | self-made |
| `neon_arcade.svg` | neon_arcade | self-made |
| `observatory.svg` | observatory | self-made |
| `palace.svg` | palace | self-made |
| `raft.svg` | raft | self-made |
| `relic.svg` | relic | self-made |
| `river.svg` | river | self-made |
| `road.svg` | road | self-made |
| `robot_sentinel.svg` | robot_sentinel | self-made |
| `ruin.svg` | ruin | self-made |
| `sea_serpent.svg` | sea_serpent | self-made |
| `ship.svg` | ship | self-made |
| `shipwreck.svg` | shipwreck | self-made |
| `skyscraper.svg` | skyscraper | self-made |
| `snow_cottage.svg` | snow_cottage | self-made |
| `subway.svg` | subway | self-made |
| `temple.svg` | temple | self-made |
| `thing.svg` | thing | self-made |
| `throne_room.svg` | throne_room | self-made |
| `tower.svg` | tower | self-made |
| `treasure.svg` | treasure | self-made |
| `village.svg` | village | self-made |
| `volcano.svg` | volcano | self-made |
| `watchtower.svg` | watchtower | self-made |
| `wolf_pack.svg` | wolf_pack | self-made |
| `yeti.svg` | yeti | self-made |
| `unknown.svg` | fallback for a role with no icon | self-made |
| `robot.svg` | the player's robot | self-made |
| `giant_hand.svg` | a hand reaching over the table (giants layer) | self-made |
