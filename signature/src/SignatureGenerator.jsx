import { useState, useRef } from "react";
import Alert from "./components/Alert";
import { FormattedInput } from "@buttercup/react-formatted-input";
import "./assets/styles/SignatureGenerator.css";

function App() {
  const [name, setName] = useState("");
  const [showPn, setShowPn] = useState(false);
  const [pronouns1, setPronouns1] = useState("");
  const [pronouns2, setPronouns2] = useState("");
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [phoneValue, setPhoneValue] = useState();
  const [address1, setAddress1] = useState("");
  const [address2, setAddress2] = useState("");

  const [fbUrl, setFbUrl] = useState("https://www.facebook.com/colbycollege/");
  const [instaUrl, setInstaUrl] = useState(
    "https://www.instagram.com/colbycollege/"
  );
  const [twitUrl, setTwitUrl] = useState("https://twitter.com/ColbyCollege/");
  const [liUrl, setLiUrl] = useState(
    "https://www.linkedin.com/school/colby-college/"
  );
  const [ytUrl, setYtUrl] = useState(
    "https://www.youtube.com/user/colbycollege/"
  );
  const [cnUrl, setCnUrl] = useState("https://news.colby.edu/");

  const [showSocial, setShowSocial] = useState(false);
  const [fbChecked, setFbChecked] = useState(true);
  const [twitChecked, setTwitChecked] = useState(true);
  const [instaChecked, setInstaChecked] = useState(true);
  const [liChecked, setLiChecked] = useState(true);
  const [ytChecked, setYtChecked] = useState(true);
  const [cnChecked, setCnChecked] = useState(true);

  const [alert, setAlert] = useState("false");

  const tableRef = useRef();

  const phonePattern = [
    { char: /\d/, repeat: 3 },
    { exactly: "-" },
    { char: /\d/, repeat: 3 },
    { exactly: "-" },
    { char: /\d/, repeat: 4 },
  ];

  const copy = () => {
    window.getSelection().removeAllRanges();
    const range = document.createRange();
    range.selectNode(tableRef.current);
    window.getSelection().addRange(range);
    document.execCommand("copy");

    window.getSelection().removeAllRanges();
    setAlert(true);
    setTimeout(() => {
      setAlert(false);
    }, 1900);
  };

  return (
    <div>
      {alert === true ? <Alert /> : ""}
      <div className="signature-app-container">
        <aside>
          <form className="signature-form">
            <article>
              <header>
                <h1>
                  Colby Email Signature Generator{" "}
                  <span className="version">v4</span>
                </h1>
              </header>
              <div>
                <ul>
                  <li>
                    <p>
                      Use the fields below to input your information. The
                      preview will change as you type.
                    </p>
                  </li>
                  <li>
                    <p>
                      Once everything looks good, use the copy button to copy
                      the signature to your clipboard.
                    </p>
                  </li>
                  <li>
                    <p>
                      Paste your new signature into the signature box in Gmail
                      settings (Gmail &rarr; Settings &rarr; General &rarr;
                      Signature)
                    </p>
                  </li>
                </ul>
              </div>
            </article>
            <label htmlFor="name">Name:</label>
            <input
              className="gen-input"
              type="text"
              id="name"
              placeholder="Name"
              onChange={(e) => setName(e.target.value)}
            ></input>
            <label htmlFor="pronouns">Pronouns:</label>
            <div style={{ width: "100%" }}>
              <input
                style={{ marginRight: "0.75rem", padding: "0", width: "auto" }}
                type="checkbox"
                onChange={() => setShowPn(!showPn)}
              ></input>
              <input
                style={{ marginRight: "0.25rem", width: "50px" }}
                type="text"
                id="pronouns"
                className="gen-input"
                placeholder="He"
                disabled={showPn === false}
                onChange={(e) => setPronouns1(e.target.value)}
              ></input>
              <span style={{ color: "white" }}>/</span>
              <input
                style={{ marginLeft: "0.25rem", width: "50px" }}
                type="text"
                id="pronouns2"
                className="gen-input"
                placeholder="Him"
                disabled={showPn === false}
                onChange={(e) => setPronouns2(e.target.value)}
              ></input>
            </div>
            <label htmlFor="title">Title:</label>
            <input
              className="gen-input"
              type="text"
              id="title"
              placeholder="Title"
              onChange={(e) => setTitle(e.target.value)}
            ></input>
            <label htmlFor="dept">Department:</label>
            <input
              className="gen-input"
              type="text"
              id="dept"
              placeholder="Communications"
              onChange={(e) => setDepartment(e.target.value)}
            ></input>
            <label htmlFor="phone">Phone Number:</label>
            <FormattedInput
              className="formatted-input gen-input"
              format={phonePattern}
              value={phoneValue}
              onChange={(formattedValue, raw) => {
                setPhoneValue(formattedValue);
              }}
              placeholder="0123456789"
            />
            <label htmlFor="address1">Address Ln 1:</label>
            <input
              className="gen-input"
              type="text"
              id="address1"
              placeholder="4000 Mayflower Hill"
              onChange={(e) => setAddress1(e.target.value)}
            ></input>
            <label htmlFor="address2">Address Ln 2:</label>
            <input
              className="gen-input"
              type="text"
              id="address2"
              placeholder="Waterville, ME 04901"
              onChange={(e) => setAddress2(e.target.value)}
            ></input>
            <div
              onClick={() => setShowSocial(!showSocial)}
              style={{
                width: "100%",
                margin: "1rem 0",
                display: "flex",
                flexDirection: "row",
                justifyContent: "start",
                alignItems: "center",
                color: "white",
              }}
            >
              <label className="social-label">Social icons</label>
              {showSocial === true ? (
                <span className="material-icons-sharp arrow">expand_more</span>
              ) : (
                <span className="material-icons-sharp arrow">
                  navigate_next
                </span>
              )}
            </div>

            {showSocial && (
              <form style={{ paddingBottom: "1.5rem" }}>
                <span
                  style={{
                    display: "flex",
                    justifyContent: "start",
                    alignItems: "center",
                  }}
                >
                  <input
                    style={{ width: "auto", marginRight: "0.75rem" }}
                    type="checkbox"
                    checked={fbChecked}
                    onChange={() => setFbChecked(!fbChecked)}
                  />
                  <label htmlFor="fb">Facebook:</label>
                </span>
                <input
                  id="fb"
                  className="social-input gen-input"
                  type="text"
                  disabled={fbChecked === false}
                  defaultValue={fbUrl}
                  onChange={(e) => setFbUrl(e.target.value)}
                ></input>

                <span
                  style={{
                    display: "flex",
                    justifyContent: "start",
                    alignItems: "center",
                  }}
                >
                  <input
                    style={{ width: "auto", marginRight: "0.75rem" }}
                    type="checkbox"
                    checked={instaChecked === true}
                    onChange={() => setInstaChecked(!instaChecked)}
                  />
                  <label htmlFor="insta">Instagram:</label>
                </span>
                <input
                  id="insta"
                  className="social-input gen-input"
                  type="text"
                  disabled={instaChecked === false}
                  defaultValue={instaUrl}
                  onChange={(e) => setInstaUrl(e.target.value)}
                ></input>

                <span
                  style={{
                    display: "flex",
                    justifyContent: "start",
                    alignItems: "center",
                  }}
                >
                  <input
                    style={{ width: "auto", marginRight: "0.75rem" }}
                    type="checkbox"
                    checked={twitChecked === true}
                    onChange={() => setTwitChecked(!twitChecked)}
                  />
                  <label htmlFor="twit">Twitter:</label>
                </span>
                <input
                  id="twit"
                  className="social-input gen-input"
                  type="text"
                  disabled={twitChecked === false}
                  defaultValue={twitUrl}
                  onChange={(e) => setTwitUrl(e.target.value)}
                ></input>

                <span
                  style={{
                    display: "flex",
                    justifyContent: "start",
                    alignItems: "center",
                  }}
                >
                  <input
                    style={{ width: "auto", marginRight: "0.75rem" }}
                    type="checkbox"
                    checked={liChecked === true}
                    onChange={() => setLiChecked(!liChecked)}
                  />
                  <label htmlFor="li">LinkedIn:</label>
                </span>
                <input
                  id="li"
                  className="social-input gen-input"
                  type="text"
                  disabled={liChecked === false}
                  defaultValue={liUrl}
                  onChange={(e) => setLiUrl(e.target.value)}
                ></input>

                <span
                  style={{
                    display: "flex",
                    justifyContent: "start",
                    alignItems: "center",
                  }}
                >
                  <input
                    style={{ width: "auto", marginRight: "0.75rem" }}
                    type="checkbox"
                    checked={ytChecked === true}
                    onChange={() => setYtChecked(!ytChecked)}
                  />
                  <label htmlFor="yt">YouTube:</label>
                </span>
                <input
                  id="yt"
                  className="social-input gen-input"
                  type="text"
                  disabled={ytChecked === false}
                  defaultValue={ytUrl}
                  onChange={(e) => setYtUrl(e.target.value)}
                ></input>

                <span
                  style={{
                    display: "flex",
                    justifyContent: "start",
                    alignItems: "center",
                  }}
                >
                  <input
                    id="cn"
                    style={{ width: "auto", marginRight: "0.75rem" }}
                    type="checkbox"
                    checked={cnChecked === true}
                    onChange={() => setCnChecked(!cnChecked)}
                  />
                  <label htmlFor="cn">Colby News</label>
                </span>
              </form>
            )}
          </form>
        </aside>
        <div className="display-container">
          <div className="display-container-inner">
            <div>
              <table
                ref={tableRef}
                role="presentation"
                cellSpacing="0"
                cellPadding="0"
                border="0"
                tabIndex={0}
                style={{
                  borderCollapse: "collapse",
                  border: "none",
                }}
              >
                <tbody style={{ border: "none" }}>
                  <tr style={{ border: "none" }}>
                    <td
                      style={{
                        verticalAlign: "top",
                        border: "none",
                      }}
                      className="logo-cell"
                    >
                      <a
                        href="https://www.colby.edu"
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          border: "none",
                          display: "flex",
                          justifyContent: "center",
                          alignItems: "flex-start",
                        }}
                      >
                        <img
                          src="https://identity.colby.edu/email-signature/colby-logo.png"
                          alt="Colby"
                          className="logo"
                          width="96px"
                          style={{
                            display: "inline-block",
                            border: "none",
                            minWidth: "96px",
                          }}
                        />
                      </a>
                    </td>
                    <td style={{ border: "none" }}>
                      <table
                        cellSpacing="0"
                        cellPadding="0"
                        border="0"
                        style={{
                          borderCollapse: "collapse",
                          border: "none",
                          marginTop: "12px",
                        }}
                      >
                        <tbody
                          className="signature-container"
                          style={{ border: "none" }}
                        >
                          <tr style={{ border: "none" }}>
                            <td style={{ border: "none" }}>
                              <table
                                cellSpacing="0"
                                cellPadding="0"
                                border="0"
                                style={{
                                  borderCollapse: "collapse",
                                  border: "none",
                                  marginLeft: "15px",
                                }}
                              >
                                <tbody>
                                  <tr style={{ border: "none" }}>
                                    <td
                                      className="name-output"
                                      style={{
                                        border: "none",
                                      }}
                                    >
                                      <p
                                        style={{
                                          border: "none",
                                          whiteSpace: "nowrap",
                                          marginRight: "1rem",
                                        }}
                                        className="output bold"
                                      >
                                        {name}
                                      </p>
                                    </td>
                                    <td
                                      style={{
                                        border: "none",
                                      }}
                                    >
                                      {showPn === true ? (
                                        <p
                                          style={{
                                            border: "none",
                                            whiteSpace: "nowrap",
                                          }}
                                          className="output bold"
                                        >{`(${pronouns1}/${pronouns2})`}</p>
                                      ) : (
                                        ""
                                      )}
                                    </td>
                                  </tr>
                                </tbody>
                              </table>
                            </td>
                          </tr>
                          <tr style={{ border: "none" }}>
                            <td style={{ border: "none" }}>
                              <p
                                className="output bold"
                                style={{
                                  border: "none",
                                  // whiteSpace: 'nowrap',
                                  marginLeft: "15px",
                                }}
                              >
                                {title}
                              </p>
                            </td>
                          </tr>
                          <tr style={{ border: "none" }}>
                            <td style={{ border: "none" }}>
                              <p
                                className="output"
                                style={{
                                  border: "none",
                                  whiteSpace: "nowrap",
                                  marginLeft: "15px",
                                }}
                              >
                                {department}
                              </p>
                            </td>
                          </tr>
                          <tr style={{ border: "none" }}>
                            <td style={{ border: "none" }}>
                              <p
                                className="output"
                                style={{
                                  border: "none",
                                  whiteSpace: "nowrap",
                                  marginLeft: "15px",
                                }}
                              >
                                {phoneValue}
                              </p>
                            </td>
                          </tr>
                          <tr style={{ border: "none" }}>
                            <td style={{ border: "none" }}>
                              <p
                                className="output"
                                style={{
                                  border: "none",
                                  whiteSpace: "nowrap",
                                  marginLeft: "15px",
                                }}
                              >
                                {address1}
                              </p>
                            </td>
                          </tr>
                          <tr style={{ border: "none" }}>
                            <td style={{ border: "none" }}>
                              <p
                                className="output"
                                style={{
                                  border: "none",
                                  whiteSpace: "nowrap",
                                  marginLeft: "15px",
                                }}
                              >
                                {address2}
                              </p>
                            </td>
                          </tr>
                          <tr
                            style={{
                              border: "none",
                            }}
                          >
                            <td style={{ border: "none" }}>
                              <table
                                style={{
                                  marginTop: "14px",
                                  marginLeft: "15px",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                <tbody>
                                  <tr>
                                    {fbChecked === true ? (
                                      <td
                                        style={{
                                          border: "none",
                                        }}
                                      >
                                        <a
                                          href={fbUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            border: "none",
                                          }}
                                        >
                                          <img
                                            src="https://identity.colby.edu/email-signature/fb-white.jpg"
                                            alt="Facebook"
                                            style={{
                                              paddingRight: "10px",
                                              float: "left",
                                            }}
                                          />
                                        </a>
                                      </td>
                                    ) : (
                                      ""
                                    )}
                                    {instaChecked === true ? (
                                      <td
                                        style={{
                                          border: "none",
                                        }}
                                      >
                                        <a
                                          href={instaUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            border: "none",
                                          }}
                                        >
                                          <img
                                            src="https://identity.colby.edu/email-signature/insta-white.jpg"
                                            alt="Instagram"
                                            style={{
                                              paddingRight: "10px",
                                              float: "left",
                                            }}
                                          />
                                        </a>
                                      </td>
                                    ) : (
                                      ""
                                    )}
                                    {twitChecked === true ? (
                                      <td
                                        style={{
                                          border: "none",
                                        }}
                                      >
                                        <a
                                          href={twitUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            border: "none",
                                          }}
                                        >
                                          <img
                                            src="https://identity.colby.edu/email-signature/twit-white.jpg"
                                            alt="Twitter"
                                            style={{
                                              paddingRight: "10px",
                                              float: "left",
                                            }}
                                          />
                                        </a>
                                      </td>
                                    ) : (
                                      ""
                                    )}
                                    {liChecked === true ? (
                                      <td
                                        style={{
                                          border: "none",
                                        }}
                                      >
                                        <a
                                          href={liUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            border: "none",
                                          }}
                                        >
                                          <img
                                            src="https://identity.colby.edu/email-signature/li-white.jpg"
                                            alt="LinkedIn"
                                            style={{
                                              paddingRight: "10px",
                                              float: "left",
                                            }}
                                          />
                                        </a>
                                      </td>
                                    ) : (
                                      ""
                                    )}
                                    {ytChecked === true ? (
                                      <td
                                        style={{
                                          border: "none",
                                        }}
                                      >
                                        <a
                                          href={ytUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            border: "none",
                                          }}
                                        >
                                          <img
                                            src="https://identity.colby.edu/email-signature/yt-white.jpg"
                                            alt="YouTube"
                                            style={{
                                              paddingRight: "10px",
                                              float: "left",
                                            }}
                                          />
                                        </a>
                                      </td>
                                    ) : (
                                      ""
                                    )}
                                    {cnChecked === true ? (
                                      <td
                                        style={{
                                          border: "none",
                                        }}
                                      >
                                        <a
                                          href={cnUrl}
                                          target="_blank"
                                          rel="noreferrer"
                                          style={{
                                            border: "none",
                                          }}
                                        >
                                          <img
                                            src="https://identity.colby.edu/email-signature/cn-white.jpg"
                                            alt="Colby News"
                                            style={{
                                              paddingRight: "10px",
                                              float: "left",
                                            }}
                                          />
                                        </a>
                                      </td>
                                    ) : (
                                      ""
                                    )}
                                  </tr>
                                </tbody>
                              </table>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="copy-container">
              <button type="button" className="copy" onClick={copy}>
                Copy
              </button>
            </div>
          </div>
        </div>
      </div>
      <footer>
        <div>
          <div className="footer-container">
            <div className="footer-container-inner">
              <div className="footer-logo-container">
                <div>
                  <a href="/">
                    <img
                      className="footer-logo"
                      src="images/COLBY_logotype_white.png"
                      alt="Colby Logo"
                    />
                  </a>
                </div>
                <div className="hidden logo-subtext">
                  Office of Communications
                </div>
              </div>
              <div className="footer-icon-container">
                <div
                  className="footer-icon"
                  onClick={() =>
                    (window.location = "https://www.facebook.com/colbycollege")
                  }
                >
                  <svg
                    height="22"
                    width="22"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 1024 1024"
                  >
                    <path
                      fill="#fff"
                      d="M1024,512C1024,229.2,794.8,0,512,0S0,229.2,0,512c0,255.6,187.2,467.4,432,505.8V660H302V512H432V399.2C432,270.9,508.4,200,625.4,200c56,0,114.6,10,114.6,10V336H675.4c-63.6,0-83.4,39.5-83.4,80v96H734L711.3,660H592v357.8C836.8,979.4,1024,767.6,1024,512Z"
                    />
                    <path
                      d="M711.3,660,734,512H592V416c0-40.5,19.8-80,83.4-80H740V210s-58.6-10-114.6-10C508.4,200,432,270.9,432,399.2V512H302V660H432v357.8a519.23,519.23,0,0,0,160,0V660Z"
                      fill="transparent"
                    />
                  </svg>
                </div>
                <div
                  className="footer-icon"
                  onClick={() =>
                    (window.location =
                      "https://www.linkedin.com/school/colby-college/")
                  }
                >
                  <svg
                    width="22"
                    height="22"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 448 448"
                  >
                    <path
                      fill="#fff"
                      d="M416,0H31.9A32.14,32.14,0,0,0,0,32.3V415.7A32.14,32.14,0,0,0,31.9,448H416a32.22,32.22,0,0,0,32-32.3V32.3A32.22,32.22,0,0,0,416,0ZM135.4,384H69V170.2h66.5V384ZM102.2,141a38.5,38.5,0,1,1,38.5-38.5A38.52,38.52,0,0,1,102.2,141ZM384.3,384H317.9V280c0-24.8-.5-56.7-34.5-56.7-34.6,0-39.9,27-39.9,54.9V384H177.1V170.2h63.7v29.2h.9c8.9-16.8,30.6-34.5,62.9-34.5,67.2,0,79.7,44.3,79.7,101.9Z"
                    />
                  </svg>
                </div>
                <div
                  className="footer-icon"
                  onClick={() =>
                    (window.location =
                      "https://www.youtube.com/user/colbycollege")
                  }
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="22"
                    height="22"
                    viewBox="0 0 176 124"
                  >
                    <path
                      d="M172.3,19.4A22.27,22.27,0,0,0,156.7,3.7C143,0,88,0,88,0S33,0,19.2,3.7A22.1,22.1,0,0,0,3.6,19.4C0,33.2,0,62,0,62s0,28.8,3.7,42.6a22.27,22.27,0,0,0,15.6,15.7C33,124,88,124,88,124s55,0,68.8-3.7a22.1,22.1,0,0,0,15.6-15.7C176,90.8,176,62,176,62S176,33.2,172.3,19.4Z"
                      fill="#fff"
                    />
                    <polygon
                      points="70 88.2 116 62 70 35.8 70 88.2"
                      fill="#575757"
                    />
                  </svg>
                </div>
                <div
                  className="footer-icon"
                  onClick={() =>
                    (window.location = "https://www.colby.edu/newsletter/")
                  }
                >
                  <svg
                    width="22"
                    height="22"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 16 12"
                  >
                    <path
                      fill="#fff"
                      d="M15,0H1A1,1,0,0,0,0,1V11a.94.94,0,0,0,1,1H15a.94.94,0,0,0,1-1V1A1,1,0,0,0,15,0Zm-.5,1.4V2.7L8,6.3,1.6,2.7V1.4ZM1.6,10.5v-6L8,8l6.5-3.5v6.1H1.6Z"
                    />
                  </svg>
                </div>
                <div
                  className="footer-icon"
                  onClick={() =>
                    (window.location =
                      "https://www.instagram.com/colbycollege/")
                  }
                >
                  <svg
                    width="22"
                    height="22"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 504 503.9"
                  >
                    <path
                      fill="#fff"
                      d="M256,49.5c67.3,0,75.2.3,101.8,1.5,24.6,1.1,37.9,5.2,46.8,8.7a78.18,78.18,0,0,1,29,18.8,77,77,0,0,1,18.8,29c3.4,8.9,7.6,22.2,8.7,46.8,1.2,26.6,1.5,34.5,1.5,101.8s-.3,75.2-1.5,101.8c-1.1,24.6-5.2,37.9-8.7,46.8a78.18,78.18,0,0,1-18.8,29,77,77,0,0,1-29,18.8c-8.9,3.4-22.2,7.6-46.8,8.7-26.6,1.2-34.5,1.5-101.8,1.5s-75.2-.3-101.8-1.5c-24.6-1.1-37.9-5.2-46.8-8.7a78.18,78.18,0,0,1-29-18.8,77,77,0,0,1-18.8-29c-3.4-8.9-7.6-22.2-8.7-46.8-1.2-26.6-1.5-34.5-1.5-101.8s.3-75.2,1.5-101.8c1.1-24.6,5.2-37.9,8.7-46.8a78.18,78.18,0,0,1,18.8-29,77,77,0,0,1,29-18.8c8.9-3.4,22.2-7.6,46.8-8.7,26.6-1.3,34.5-1.5,101.8-1.5m0-45.4c-68.4,0-77,.3-103.9,1.5S107,11.1,91,17.3A122.79,122.79,0,0,0,46.4,46.4,125,125,0,0,0,17.3,91c-6.2,16-10.5,34.3-11.7,61.2S4.1,187.6,4.1,256s.3,77,1.5,103.9,5.5,45.1,11.7,61.2a122.79,122.79,0,0,0,29.1,44.6A125,125,0,0,0,91,494.8c16,6.2,34.3,10.5,61.2,11.7s35.4,1.5,103.9,1.5,77-.3,103.9-1.5,45.1-5.5,61.2-11.7a122.79,122.79,0,0,0,44.6-29.1,125,125,0,0,0,29.1-44.6c6.2-16,10.5-34.3,11.7-61.2s1.5-35.4,1.5-103.9-.3-77-1.5-103.9-5.5-45.1-11.7-61.2a122.79,122.79,0,0,0-29.1-44.6,125,125,0,0,0-44.6-29.1C405.2,11,386.9,6.7,360,5.5S324.4,4.1,256,4.1Z"
                      transform="translate(-4.1 -4.1)"
                    />
                    <path
                      fill="#fff"
                      d="M256,126.6A129.4,129.4,0,1,0,385.4,256,129.42,129.42,0,0,0,256,126.6ZM256,340a84,84,0,1,1,84-84A84,84,0,0,1,256,340Z"
                      transform="translate(-4.1 -4.1)"
                    />
                    <circle fill="#fff" cx="386.4" cy="117.4" r="30.2" />
                  </svg>
                </div>
                <div
                  className="footer-icon"
                  onClick={() =>
                    (window.location = "https://twitter.com/ColbyCollege")
                  }
                >
                  <svg
                    height="22"
                    width="22"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 400 324"
                  >
                    <path
                      fill="#fff"
                      d="M126,324c150.36,0,232.63-124.69,232.63-232.64,0-3.5,0-7-.16-10.52a166.49,166.49,0,0,0,40.82-42.41,165.81,165.81,0,0,1-47,12.91,82.23,82.23,0,0,0,36-45.28,162.73,162.73,0,0,1-52,19.77,81.78,81.78,0,0,0-141.43,56,90.69,90.69,0,0,0,2.07,18.65A232.19,232.19,0,0,1,28.4,15,82.09,82.09,0,0,0,53.76,124.21a82.87,82.87,0,0,1-37-10.2v1.11a81.93,81.93,0,0,0,65.54,80.2,82.39,82.39,0,0,1-36.84,1.44,81.75,81.75,0,0,0,76.38,56.76A164,164,0,0,1,20.27,288.6,158.72,158.72,0,0,1,.82,287.49,232.58,232.58,0,0,0,126,324"
                    />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
