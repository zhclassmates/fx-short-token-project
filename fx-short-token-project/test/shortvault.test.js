const { expect } = require("chai");
const { ethers } = require("hardhat");

const toWei = (v) => ethers.utils.parseUnits(v, 18);

async function deployFixture({
  price = "100",
  leverage = "3",
  minCR = "1.0",
  liqCR = "1.0",
} = {}) {
  const [deployer, user] = await ethers.getSigners();

  const MockCollateralToken = await ethers.getContractFactory("MockCollateralToken");
  const collateral = await MockCollateralToken.deploy();
  await collateral.deployed();

  const ShortToken = await ethers.getContractFactory("ShortToken");
  const sToken = await ShortToken.deploy("Short Token", "sTKN");
  await sToken.deployed();

  const MockOracle = await ethers.getContractFactory("MockOracle");
  const oracle = await MockOracle.deploy(toWei(price));
  await oracle.deployed();

  const ShortVaultV1 = await ethers.getContractFactory("ShortVaultV1");
  const vault = await ShortVaultV1.deploy(
    collateral.address,
    sToken.address,
    oracle.address,
    toWei(leverage),
    toWei(minCR),
    toWei(liqCR)
  );
  await vault.deployed();

  await sToken.transferOwnership(vault.address);

  await collateral.connect(user).mint(toWei("1000"));
  await collateral.connect(user).approve(vault.address, toWei("1000"));

  return { deployer, user, collateral, sToken, oracle, vault };
}

describe("ShortVaultV1", function () {
  it("mints and redeems sToken at NAV", async function () {
    const { user, collateral, sToken, vault } = await deployFixture();

    await vault.connect(user).deposit(toWei("100"));
    expect(await sToken.balanceOf(user.address)).to.equal(toWei("100"));

    const before = await collateral.balanceOf(user.address);
    await vault.connect(user).redeem(toWei("50"));
    const after = await collateral.balanceOf(user.address);

    expect(after.sub(before)).to.equal(toWei("50"));
  });

  it("updates index when price moves", async function () {
    const { user, oracle, vault } = await deployFixture({ leverage: "2" });

    await vault.connect(user).deposit(toWei("100"));

    await oracle.setPrice(toWei("110")); // +10%
    await vault.updateIndex();

    const index = await vault.index();
    // expected factor = 1 - 2 * 0.1 = 0.8
    expect(index).to.equal(toWei("0.8"));
  });

  it("triggers liquidation on extreme adverse move", async function () {
    const { user, oracle, vault, sToken, collateral } = await deployFixture({ leverage: "3" });

    await vault.connect(user).deposit(toWei("100"));
    await oracle.setPrice(toWei("50")); // -50% => index would rise to 2.5

    await vault.updateIndex();

    expect(await vault.status()).to.equal(1); // Liquidation
    expect(await vault.liquidationIndex()).to.equal(toWei("1"));

    const before = await collateral.balanceOf(user.address);
    await vault.connect(user).redeem(toWei("100"));
    const after = await collateral.balanceOf(user.address);

    expect(after.sub(before)).to.equal(toWei("100"));
    expect(await sToken.balanceOf(user.address)).to.equal(0);
  });
});
