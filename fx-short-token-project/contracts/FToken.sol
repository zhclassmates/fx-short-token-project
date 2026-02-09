// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title FToken
 * @notice f(x) 协议中的稳定份额代币 (fBTC)
 * @dev 目标 beta ≈ 0.1，吸收标的资产 10% 的波动
 */
contract FToken is ERC20, Ownable {
    
    // Vault 地址（唯一有权铸造/燃烧的合约）
    address public vault;
    
    // 事件
    event VaultUpdated(address indexed oldVault, address indexed newVault);
    
    constructor(string memory name, string memory symbol) ERC20(name, symbol) {}
    
    /**
     * @notice 设置 Vault 地址（仅一次）
     */
    function setVault(address _vault) external onlyOwner {
        require(_vault != address(0), "Vault=0");
        require(vault == address(0), "Vault already set");
        vault = _vault;
        emit VaultUpdated(address(0), _vault);
    }
    
    /**
     * @notice 更改 Vault 地址（紧急情况下）
     */
    function changeVault(address _vault) external onlyOwner {
        require(_vault != address(0), "Vault=0");
        address oldVault = vault;
        vault = _vault;
        emit VaultUpdated(oldVault, _vault);
    }
    
    /**
     * @notice 铸造代币（仅 Vault 可调用）
     */
    function mint(address to, uint256 amount) external {
        require(msg.sender == vault, "Only vault");
        require(to != address(0), "To=0");
        require(amount > 0, "Amount=0");
        _mint(to, amount);
    }
    
    /**
     * @notice 燃烧代币（仅 Vault 可调用）
     */
    function burn(address from, uint256 amount) external {
        require(msg.sender == vault, "Only vault");
        require(amount > 0, "Amount=0");
        _burn(from, amount);
    }
    
    /**
     * @notice 用户自我燃烧
     */
    function burn(uint256 amount) external {
        require(amount > 0, "Amount=0");
        _burn(msg.sender, amount);
    }
    
    function decimals() public pure override returns (uint8) {
        return 18;
    }
}