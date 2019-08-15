pragma solidity ^0.5.0;

contract Lottery {
    final address master;
    uint@master secret;
    mapping(address!x => uint@x) bets;

    bool revealed;
    uint published_secret;
    address winner;

    constructor(uint@me s) public {
        master = me;
        secret = s;
        revealed = false;
    }

    function bet(uint@me val) public {
        require(me != master);
        require(!revealed);
        bets[me] = val;
    }

    function publish_secret() public {
        require(master == me);
        require(!revealed);
        revealed = true;
        published_secret = reveal(secret, all);
    }

    function claim_winner() public {
        require(revealed && (me != master));
        require(reveal(bets[me] == published_secret, all));
        winner = me;
        // send money here
    }
}