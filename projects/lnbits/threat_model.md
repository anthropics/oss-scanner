# LNbits threat model

## What this project does and where untrusted input enters

LNbits handles money through Bitcoin Lightning Network payments and onchain
Bitcoin transactions. It lets individuals and communities manage wallets, receive
and send payments, and add functionality through extensions. It connects to
funding sources and other services on behalf of its users. Security failures can
cause real financial loss.

Input from visitors, users, payment requests, uploaded content, extensions and
external services may be malicious or misleading. Being logged in does not make
a user's input trustworthy.

Access must stay within the permissions granted. Access to one wallet must not
expose another user's funds or private information. Permission to view a wallet
or receive payments must not allow spending. Shared access must respect the
owner's choices.

Regular users, administrators and the instance owner have different powers.
Check these boundaries against the project's current documented behavior.
Extensions must respect the access and isolation guarantees of their installation
and permission model.

## Components that matter most / least

The highest priorities are:

- Protecting funds from unauthorized spending, redirection or loss.
- Keeping balances and payment records correct when requests are repeated,
  interrupted or made at the same time.
- Preventing account takeover and access to another user's wallets or private
  information, including through login, recovery and sharing features.
- Protecting credentials, recovery information and other secrets.
- Enforcing administrative and extension permissions, including who may change
  funding sources, install extensions or authorize payments.
- Preventing untrusted content and external services from gaining unintended
  access to the server or acting with a user's authority.
- Keeping the service available, especially preventing one user's actions from
  disrupting payments or access for others.

Cosmetic issues are lower priority unless they mislead users about payments,
permissions or other security decisions.

## How to exercise it

Use the project's current documentation and test tools with isolated test data
and simulated payments. Compare what visitors, ordinary users, administrators
and people with limited wallet access can do. Exercise shared wallets,
extensions, failed payments and repeated or simultaneous requests.

For each finding, explain the access and settings needed, how to reproduce it,
what should happen, what actually happens and the impact on users or operators.

## How you rate severity

Rate findings by the harm they can cause, how easily they can be exploited, the
access required and the number of users or wallets affected. State any special
conditions. Consider funds held through both the Bitcoin Lightning Network and
onchain Bitcoin wallets.

- **Critical:** Direct, practical theft or redirection of funds, exposure of
  secrets that allow spending, manipulation of balances that enables spending
  money never received, full control of the instance, or widespread permanent
  loss of access to funds. An attack requiring an ordinary user account can still
  be critical. A small balance in a test wallet does not reduce the severity of
  an attack that can steal real funds.
- **High:** Serious harm, such as account takeover, substantial exposure of
  private financial information, unauthorized administrative access or sustained
  disruption that prevents many users from using their wallets. Financial loss
  that requires significant additional conditions also belongs here; explain
  those conditions clearly.
- **Medium:** Meaningful but contained harm, such as exposure of limited private
  information, unauthorized changes that do not affect funds, or temporary
  disruption affecting a small number of users. There is no demonstrated path
  to unauthorized spending or account takeover.
- **Low:** Minor security impact, such as limited exposure of non-sensitive
  information or a brief inconvenience affecting one user. There is no
  demonstrated risk to funds, account control or sensitive private information.

## Anything to leave alone
