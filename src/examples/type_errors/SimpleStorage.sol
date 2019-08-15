pragma solidity ^0.5.0;

// simple getter/setter contract
contract SimpleStorage {
    uint@all storedData;

    function set(uint@me x) public {
        storedData = x;
    }

    function get() public returns (uint@all) {
        return storedData;
    }
}

