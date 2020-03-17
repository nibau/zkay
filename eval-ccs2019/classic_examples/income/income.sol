pragma solidity ^0.5.0;

// Description: Decide eligibility for welfare programs
// Domain: Welfare
contract Income {
	uint MAX_INCOME = 40000;

	mapping(address!x => uint@x) allIncomes;
	mapping(address => bool) incomeDeclared;
	mapping(address => bool) isEligible;

	function init() public {
		allIncomes[me] = 0;
	}

	function registerIncome(uint@me newIncome) public {
		allIncomes[me] = allIncomes[me] + newIncome;
		incomeDeclared[me] = true;
	}

	function checkEligibility() public {
		require(incomeDeclared[me]);
		isEligible[me] = reveal(MAX_INCOME >= allIncomes[me], all);
	}
}