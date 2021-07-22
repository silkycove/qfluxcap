OPENQASM 2.0;
include "qelib1.inc";

qreg q[3];
creg c[3];

ry(pi/3) q[0];
barrier q[0],q[1],q[2];

h q[1];
cx q[1],q[2];
barrier q[0],q[1],q[2];

cx q[0],q[1];
h q[0];
barrier q[0],q[1],q[2];

cz q[0],q[2];
cx q[1],q[2];

measure q[2] -> c[2];