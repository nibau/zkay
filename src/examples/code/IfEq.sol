pragma solidity ^0.5.0;

contract IfEq {
    final address master;
    uint@master a;
    uint@master b;

    constructor() public {
        master = me;
    }

    function f() public {
        require(master == me);
        uint@me p;
        p = a == b ? 1 : 0;
    }
}
