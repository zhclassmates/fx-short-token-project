// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/Ownable.sol";

contract MockOracle is Ownable {
    uint256 private price; // 1e18

    constructor(uint256 _price) {
        price = _price;
    }

    function setPrice(uint256 _price) external onlyOwner {
        price = _price;
    }

    function getPrice() external view returns (uint256) {
        return price;
    }
}
