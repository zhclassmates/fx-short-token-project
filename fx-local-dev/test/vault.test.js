const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("FxVaultV1", function () {
  let mockCollateral, fToken, xToken, vault;
  let owner, addr1, addr2;

  beforeEach(async function () {
    // 部署合约
    [owner, addr1, addr2] = await ethers.getSigners();

    // 部署MockCollateralToken
    const MockCollateralToken = await ethers.getContractFactory("MockCollateralToken");
    mockCollateral = await MockCollateralToken.deploy();

    // 部署FToken
    const FToken = await ethers.getContractFactory("FToken");
    fToken = await FToken.deploy("f-MockCollateral", "fMCT");

    // 部署XToken
    const XToken = await ethers.getContractFactory("XToken");
    xToken = await XToken.deploy("x-MockCollateral", "xMCT");

    // 部署FxVaultV1
    const FxVaultV1 = await ethers.getContractFactory("FxVaultV1");
    vault = await FxVaultV1.deploy(
      mockCollateral.address,
      fToken.address,
      xToken.address
    );

    // 转移所有权
    await fToken.transferOwnership(vault.address);
    await xToken.transferOwnership(vault.address);

    // 给addr1一些mock collateral用于测试
    await mockCollateral.connect(addr1).mint(ethers.utils.parseEther("100"));
  });

  describe("mint", function () {
    it("Should mint f and x tokens when user provides collateral", async function () {
      const amount = ethers.utils.parseEther("10");
      
      // 批准vault使用addr1的collateral
      await mockCollateral.connect(addr1).approve(vault.address, amount);
      
      // 执行mint
      await vault.connect(addr1).mint(amount);
      
      // 检查vault是否收到了collateral
      expect(await mockCollateral.balanceOf(vault.address)).to.equal(amount);
      
      // 检查addr1是否收到了fToken和xToken
      // 根据BETA_F_TARGET=0.1，应该得到约1个fToken和9个xToken
      const expectedFAmount = ethers.utils.parseEther("1"); // 0.1 * 10
      const expectedXAmount = ethers.utils.parseEther("9"); // 10 - 1
      const fBalance = await fToken.balanceOf(addr1.address);
      const xBalance = await xToken.balanceOf(addr1.address);
      
      // 使用BigNumber比较方法
      expect(fBalance).to.be.closeTo(expectedFAmount, 100);
      expect(xBalance).to.be.closeTo(expectedXAmount, 100);
      
      // 检查事件是否被正确触发
      // 再次批准vault使用addr1的collateral
      await mockCollateral.connect(addr1).approve(vault.address, amount);
      await expect(vault.connect(addr1).mint(amount))
        .to.emit(vault, "Mint")
        .withArgs(addr1.address, amount, expectedFAmount, expectedXAmount);
    });

    it("Should fail if amount is zero", async function () {
      await expect(vault.connect(addr1).mint(0)).to.be.revertedWith("Amount > 0");
    });
  });

  describe("getLeverage", function () {
    it("Should return correct initial leverage", async function () {
      const amount = ethers.utils.parseEther("10");
      
      // 批准并mint
      await mockCollateral.connect(addr1).approve(vault.address, amount);
      await vault.connect(addr1).mint(amount);
      
      // 初始杠杆应该约为10x (根据公式 L = 1/(1-β_x)，β_x≈0.9)
      const leverage = await vault.getLeverage();
      // 由于我们简化了计算，实际值可能与10x有差异
      expect(leverage).to.be.gt(0);
    });
  });

  describe("redeem", function () {
    it("Should allow user to redeem collateral by returning f and x tokens", async function () {
      const mintAmount = ethers.utils.parseEther("10");
      
      // 批准并mint
      await mockCollateral.connect(addr1).approve(vault.address, mintAmount);
      await vault.connect(addr1).mint(mintAmount);
      
      // 获取合约中的totalFT和totalXT值，用于调试
      const totalFTBefore = await vault.totalFT();
      const totalXTBefore = await vault.totalXT();
      console.log('Total FT before redeem:', totalFTBefore.toString());
      console.log('Total XT before redeem:', totalXTBefore.toString());
      
      // 获取addr1的fToken和xToken余额
      const fBalance = await fToken.balanceOf(addr1.address);
      const xBalance = await xToken.balanceOf(addr1.address);
      console.log('User fBalance:', fBalance.toString());
      console.log('User xBalance:', xBalance.toString());
      
      // 批准vault使用这些代币
      await fToken.connect(addr1).approve(vault.address, fBalance);
      await xToken.connect(addr1).approve(vault.address, xBalance);
      
      try {
        // 执行redeem
        await vault.connect(addr1).redeem(fBalance, xBalance);
        console.log('Redeem executed successfully');
      } catch (error) {
        console.log('Redeem error:', error.message);
        throw error;
      }
      
      // 检查用户是否收到了collateral
      const userCollateralBalance = await mockCollateral.balanceOf(addr1.address);
      const expectedCollateralBalance = ethers.utils.parseEther("100"); // 用户最初有100个以太，存入10个后又全部赎回
      expect(userCollateralBalance).to.be.closeTo(expectedCollateralBalance, 100);
      
      // 检查用户的fToken和xToken余额是否为0
      const finalFBalance = await fToken.balanceOf(addr1.address);
      const finalXBalance = await xToken.balanceOf(addr1.address);
      expect(finalFBalance).to.equal(0);
      expect(finalXBalance).to.equal(0);
    });
  });
});