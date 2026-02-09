// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MockCollateralToken is ERC20, Ownable {
    constructor() ERC20("Mock Collateral Token", "MCT") {
        // 初始供应量为0，owner可以mint
    }
    
    // 允许任何人mint测试代币（仅用于测试环境）
    function mint(uint256 amount) external {
        _mint(msg.sender, amount);
    }
    
    // 仅owner可以burn代币
    function burn(address from, uint256 amount) external onlyOwner {
        _burn(from, amount);
    }
}