pragma solidity ^0.5.0;

contract FinalUseAfterWrite {

    final address owner;
    final uint@owner value;

    constructor(uint@me v) public{
        owner = me;
        value = v;
    }

}
