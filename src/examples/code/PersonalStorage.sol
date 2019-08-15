pragma solidity ^0.5.0;

contract PersonalStorage {
    mapping(address!x => uint@x) values;

    function set(uint@me x) public {
        values[me] = x;
    }

    function get() public returns (uint@me) {
        return values[me];
    }
}
