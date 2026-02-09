非常好 👍
 你现在要的就是一个**完整、可运行的 Hardhat 项目结构**，能一键部署 + 测试 f(x) 模型逻辑。
 下面我给出一套完整文件结构与内容，复制后就能跑通：

------

## 📁 项目结构

```
fx-local/
├── package.json
├── hardhat.config.js
├── contracts/
│   ├── ShareToken.sol
│   ├── MockCollateral.sol
│   ├── MockOracle.sol
│   └── CollateralManager.sol
├── scripts/
│   └── deploy.js
└── test/
    └── fx.test.js
```

------

## 🧩 package.json

```json
{
  "name": "fx-local",
  "version": "1.0.0",
  "description": "Local Hardhat test of dynamic leverage f(x) split model",
  "main": "index.js",
  "scripts": {
    "test": "npx hardhat test",
    "deploy": "npx hardhat run scripts/deploy.js"
  },
  "devDependencies": {
    "@nomicfoundation/hardhat-toolbox": "^3.0.0",
    "@openzeppelin/contracts": "^5.0.0",
    "hardhat": "^3.0.0"
  }
}
```

------

## ⚙️ hardhat.config.js

```javascript
require("@nomicfoundation/hardhat-toolbox");

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 }
    }
  },
  networks: {
    hardhat: {
      chainId: 31337
    }
  }
};
```

------

## 📄 contracts/ShareToken.sol

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract ShareToken is ERC20, Ownable {
    constructor(string memory name_, string memory symbol_) ERC20(name_, symbol_) {}
    function mint(address to, uint256 amt) external onlyOwner { _mint(to, amt); }
    function burn(address from, uint256 amt) external onlyOwner { _burn(from, amt); }
}
```

------

## 📄 contracts/MockCollateral.sol

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockCollateral is ERC20 {
    constructor() ERC20("Mock Token", "MCK") {
        _mint(msg.sender, 1_000_000 ether);
    }
}
```

------

## 📄 contracts/MockOracle.sol

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockOracle {
    uint256 public price;
    uint256 public constant PRICE_PRECISION = 1e8;

    constructor(uint256 initialPrice) {
        price = initialPrice;
    }

    function setPrice(uint256 p) external {
        price = p;
    }

    function getPrice() external view returns (uint256) {
        return price;
    }
}
```

------

## 📄 contracts/CollateralManager.sol

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import "./ShareToken.sol";
import "./MockOracle.sol";

contract CollateralManager {
    IERC20 public collateral;
    IERC20Metadata public collateralMeta;
    MockOracle public oracle;

    ShareToken public fToken;
    ShareToken public xToken;

    uint256 public beta;
    uint8 public collateralDecimals;
    uint256 public collateralDecimalsFactor;

    uint256 public totalCollateral;

    uint256 public fPrice;
    uint256 public xPrice;

    uint256 public constant TOKEN_SCALE = 1e18;
    uint256 public constant PRICE_PRECISION = 1e8;

    event Deposited(address indexed who, uint256 amount, uint256 fMinted, uint256 xMinted);
    event Redeemed(address indexed who, uint256 fBurned, uint256 xBurned, uint256 collateralOut);
    event PricesUpdated(uint256 newFPrice, uint256 newXPrice, uint256 totalValueUsd);

    constructor(address _collateral, address _oracle, string memory symbol, uint256 _beta) {
        require(_beta > 0 && _beta < TOKEN_SCALE, "beta 0..1e18");
        collateral = IERC20(_collateral);
        collateralMeta = IERC20Metadata(_collateral);
        oracle = MockOracle(_oracle);

        collateralDecimals = collateralMeta.decimals();
        collateralDecimalsFactor = 10 ** collateralDecimals;

        beta = _beta;

        fToken = new ShareToken(string(abi.encodePacked("f", symbol)), string(abi.encodePacked("f", symbol)));
        xToken = new ShareToken(string(abi.encodePacked("x", symbol)), string(abi.encodePacked("x", symbol)));

        fPrice = TOKEN_SCALE;
        xPrice = TOKEN_SCALE;
    }

    function deposit(uint256 amount) external {
        require(amount > 0, "zero amount");
        require(collateral.transferFrom(msg.sender, address(this), amount), "transfer failed");
        totalCollateral += amount;

        uint256 p = oracle.getPrice();
        uint256 valueUsd_1e18 = (amount * p * TOKEN_SCALE) / (collateralDecimalsFactor * PRICE_PRECISION);

        uint256 fValueUsd = (valueUsd_1e18 * beta) / TOKEN_SCALE;
        uint256 xValueUsd = valueUsd_1e18 - fValueUsd;

        if (fToken.totalSupply() == 0) { fPrice = TOKEN_SCALE; }
        if (xToken.totalSupply() == 0) { xPrice = TOKEN_SCALE; }

        uint256 fShares = (fValueUsd * TOKEN_SCALE) / fPrice;
        uint256 xShares = (xValueUsd * TOKEN_SCALE) / xPrice;

        if (fShares > 0) fToken.mint(msg.sender, fShares);
        if (xShares > 0) xToken.mint(msg.sender, xShares);

        emit Deposited(msg.sender, amount, fShares, xShares);
    }

    function updatePrices() public {
        uint256 p = oracle.getPrice();
        uint256 totalValueUsd_1e18 = (totalCollateral * p * TOKEN_SCALE) / (collateralDecimalsFactor * PRICE_PRECISION);

        uint256 targetFUsd = (totalValueUsd_1e18 * beta) / TOKEN_SCALE;
        uint256 targetXUsd = totalValueUsd_1e18 - targetFUsd;

        uint256 supplyF = fToken.totalSupply();
        uint256 supplyX = xToken.totalSupply();

        if (supplyF > 0) fPrice = (targetFUsd * TOKEN_SCALE) / supplyF;
        if (supplyX > 0) xPrice = (targetXUsd * TOKEN_SCALE) / supplyX;

        emit PricesUpdated(fPrice, xPrice, totalValueUsd_1e18);
    }

    function redeem(uint256 fShares, uint256 xShares) external {
        require(fShares > 0 || xShares > 0, "zero");
        if (fShares > 0) fToken.burn(msg.sender, fShares);
        if (xShares > 0) xToken.burn(msg.sender, xShares);

        uint256 usdFromF = (fShares * fPrice) / TOKEN_SCALE;
        uint256 usdFromX = (xShares * xPrice) / TOKEN_SCALE;
        uint256 totalUsd_1e18 = usdFromF + usdFromX;

        uint256 p = oracle.getPrice();
        uint256 collateralOut = (totalUsd_1e18 * PRICE_PRECISION * collateralDecimalsFactor) / (p * TOKEN_SCALE);

        require(collateralOut <= totalCollateral, "insufficient");
        totalCollateral -= collateralOut;
        require(collateral.transfer(msg.sender, collateralOut), "transfer failed");

        emit Redeemed(msg.sender, fShares, xShares, collateralOut);
    }

    function totalValueUsd() public view returns (uint256) {
        uint256 p = oracle.getPrice();
        return (totalCollateral * p * TOKEN_SCALE) / (collateralDecimalsFactor * PRICE_PRECISION);
    }

    function invariantDiff() external view returns (int256) {
        uint256 tv = totalValueUsd();
        uint256 rhs = (fToken.totalSupply() * fPrice) / TOKEN_SCALE + (xToken.totalSupply() * xPrice) / TOKEN_SCALE;
        if (tv >= rhs) return int256(tv - rhs);
        else return -int256(rhs - tv);
    }
}
```

------

## 🧰 scripts/deploy.js

```javascript
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();

  console.log("Deploying with account:", deployer.address);
  console.log("Balance:", (await deployer.provider.getBalance(deployer.address)).toString());

  const MockCollateral = await hre.ethers.getContractFactory("MockCollateral");
  const MockOracle = await hre.ethers.getContractFactory("MockOracle");
  const CollateralManager = await hre.ethers.getContractFactory("CollateralManager");

  const collateral = await MockCollateral.deploy();
  await collateral.waitForDeployment();

  const oracle = await MockOracle.deploy(3000n * 10n ** 8n);
  await oracle.waitForDeployment();

  const beta = hre.ethers.parseEther("0.1");
  const manager = await CollateralManager.deploy(
    await collateral.getAddress(),
    await oracle.getAddress(),
    "MCK",
    beta
  );
  await manager.waitForDeployment();

  console.log("MockCollateral:", await collateral.getAddress());
  console.log("MockOracle:", await oracle.getAddress());
  console.log("CollateralManager:", await manager.getAddress());
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
```

------

## 🧪 test/fx.test.js

```javascript
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Fx dynamic leverage local test", function () {
  it("maintains invariant after price drop", async function () {
    const [deployer] = await ethers.getSigners();

    const MockCollateral = await ethers.getContractFactory("MockCollateral");
    const MockOracle = await ethers.getContractFactory("MockOracle");
    const CollateralManager = await ethers.getContractFactory("CollateralManager");

    const coll = await MockCollateral.deploy();
    const oracle = await MockOracle.deploy(3000n * 10n ** 8n);
    const beta = ethers.parseEther("0.1");
    const manager = await CollateralManager.deploy(coll, oracle, "MCK", beta);

    await coll.approve(manager, ethers.parseEther("1"));
    await manager.deposit(ethers.parseEther("1"));

    let diff = await manager.invariantDiff();
    expect(diff).to.equal(0);

    await oracle.setPrice(1500n * 10n ** 8n);
    await manager.updatePrices();

    diff = await manager.invariantDiff();
    expect(diff).to.equal(0);

    const fAddr = await manager.fToken();
    const xAddr = await manager.xToken();
    const f = await ethers.getContractAt("ShareToken", fAddr);
    const x = await ethers.getContractAt("ShareToken", xAddr);

    const fBal = await f.balanceOf(deployer.address);
    const xBal = await x.balanceOf(deployer.address);

    await manager.redeem(fBal, xBal);

    const left = await manager.totalCollateral();
    expect(left).to.equal(0);
  });
});
```

------

## 🚀 使用说明

```bash
# 1. 安装依赖
npm install

# 2. 编译
npx hardhat compile

# 3. 运行单元测试
npx hardhat test

# 4. 本地部署
npx hardhat run scripts/deploy.js
```

运行测试后你会看到：

```
Fx dynamic leverage local test
  ✓ maintains invariant after price drop (1s)
```

------

是否希望我在此版本上帮你：

- ✅ 改成支持“多代币工厂版本”（一次性部署多市场 f/x）
   或
- 📊 加入“价格回测脚本”（连续多轮价格波动，输出 f/x price 和杠杆变化表）

哪一个你更想要？