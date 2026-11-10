# Reading node-editor screenshots

Write the graph as text **before** building anything. One line per node: `name [type] key=value`, then one line per link: `A.Out -> B.In`.

## Which editor is it
- Header says Shader Editor / Geometry Node Editor; the Output node tells you (Material Output, Group Output). A group node with a "Geometry" socket on the left and right is Geometry Nodes.

## Reading a node
- Title bar = node type (colour hints at the family: shaders green, textures orange, converters blue, inputs red, vectors purple in the default theme; geometry nodes have their own teal/blue families).
- Rows with a socket on the **left** are inputs, on the **right** outputs. A value box beside an input means it is *not linked* and that value is used.
- Dropdowns at the top of a node (e.g. `4D`, `Multiply`, `Instancer`) are node properties, not sockets: record them separately.
- Collapsed or hidden sockets are not shown but still exist; unconnected hidden ones keep defaults.
- Frames and reroutes carry no data: follow the wire through them.

## Socket colours (default theme)
grey = float, green = integer, light pink = boolean, blue-violet = vector, yellow = colour, bright green = shader, teal = geometry, orange = object, white = collection, salmon = material.

## Links
- Follow each wire from the output dot to the input it enters; note the **output name** when a node has several (`Fac` / `Color`, `Mesh` / `Instances`).
- A wire entering the *header* of an input (rather than its dot) is a mistake in the screenshot, not a rule: say so.
- Where wires overlap, count dots: each input accepts exactly one wire.

## Values
- Read digits slowly; screenshots blur `0.5` / `0.6` and `1` / `7`. Mark anything under ~10 px tall as uncertain.
- Angle fields show degrees but scripts use radians: convert with `math.radians` before putting a value in a spec.
- Ramp stops: read position and colour per stop; interpolation is in the ramp's dropdown.

## Check your transcription
Build, then run `node_text.py` on the result and diff it against your text. Any line that differs is either a build mistake or a misread: decide which by looking at the screenshot again, not by trusting the build.
